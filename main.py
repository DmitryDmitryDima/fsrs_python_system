from email.policy import default
from urllib.request import Request

from fastapi import FastAPI, Depends, Request, HTTPException, status
from pydantic import BaseModel
from fsrs import Scheduler, Card, Rating, ReviewLog, State
from datetime import datetime, timezone
from sqlmodel import Field, Session, SQLModel, create_engine, select, Column, DateTime
from uuid import UUID, uuid4

from typing import Annotated, Optional

import uvicorn


app = FastAPI()


# dto для фронтенд ответа при просмотре карточек
class RatedCard(BaseModel):
    card_id: int
    rating: str
    deck_id: int

# dto для бэкенд ответа
class BackendAnswerCard(BaseModel):
    card_id: Optional[int] = None
    front_content: Optional[str] = None
    back_content: Optional[str] = None


# dto для запроса на создание новой карточки
class NewCard(BaseModel):
    front_content: str
    back_content: str
    with_reversed: bool


# dto для запроса на создание новой колоды
class NewDeck(BaseModel):
    deck_name:str

class DeckDTO(BaseModel):

    deck_id: int
    deck_name: str









# сущность колоды для таблицы
class Deck(SQLModel, table=True):
    deck_id:int | None = Field(default=None, primary_key=True)
    user_uuid:UUID
    deck_name: str = Field(unique=True, nullable=False)


# сущность карточки для таблицы
class DatabaseCard(SQLModel, table=True):
    card_id: int | None = Field(default=None, primary_key=True)
    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime = Field(
      sa_column=Column(
          DateTime(timezone=True),
          nullable=False
      )
    )
    last_review: datetime = Field(
      sa_column=Column(
          DateTime(timezone=True),
          nullable=False
      )
    )
    front_content: str
    back_content: str

    deck: int = Field(foreign_key="deck.deck_id")



def convertFsrsEntityToDbEntity(fsrsCard:Card, request_body:NewCard, reversed: bool):
    databaseCard = DatabaseCard()
    #databaseCard.card_id = fsrsCard.card_id
    databaseCard.state = fsrsCard.state.value
    databaseCard.step = fsrsCard.step
    databaseCard.stability = fsrsCard.stability
    databaseCard.difficulty = fsrsCard.difficulty


    # аккуратнее со временем
    databaseCard.due = fsrsCard.due
    databaseCard.last_review = fsrsCard.last_review

    if not reversed:
        databaseCard.front_content = request_body.front_content
        databaseCard.back_content = request_body.back_content
    else:
        databaseCard.front_content = request_body.back_content
        databaseCard.back_content = request_body.front__content

    databaseCard.deck = request_body.deck
    return databaseCard


def convertDbEntityToFsrsCardAndMakeReview(dbCard:DatabaseCard, rating:str)->DatabaseCard:
    scheduler = Scheduler()

    # готовим карту для алгоритма
    card = Card()

    card.state = State(dbCard.state)
    card.step = dbCard.step
    card.stability = dbCard.stability
    card.difficulty = dbCard.difficulty
    card.last_review = dbCard.last_review

    ratingEnum = None

    if (rating == "Hard"):
        ratingEnum = Rating.Hard
    elif (rating == "Again"):
        ratingEnum = Rating.Again
    elif (rating == "Good"):
        ratingEnum = Rating.Good
    else:
        ratingEnum = Rating.Easy

    card, review_log = scheduler.review_card(card, ratingEnum)

    print("reviewed ", card)

    dbCard.state = card.state.value
    dbCard.step = card.step
    dbCard.stability =card.stability
    dbCard.difficulty = card.difficulty

    # аккуратнее со временем
    dbCard.due = card.due
    dbCard.last_review = card.last_review

    return dbCard












# postgres - имя пользователя
# 123 - пароль
# localhost:5432/postgres - адрес базы данных с таблицами
postgres_url = "postgresql://postgres:123@localhost:5432/postgres"


engine = create_engine(postgres_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

create_db_and_tables()










# список колод для юзера
# для наглядности можно возвращать количество доступных к изучению карточек

#todo число карточек, доступных к изучению для каждой колоды
@app.get("/getDecks")
def getDecks(request:Request, session:SessionDep):
    role = request.headers.get("role")
    if (role != "ADMIN" and role != "USER"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_uuid = request.headers.get("uuid")

    statement = select(Deck).filter(Deck.user_uuid==user_uuid)

    deck_list = session.exec(statement).all()

    answer = [DeckDTO(deck_id = x.deck_id, deck_name =  x.deck_name) for x in deck_list]


    return answer









# добавляем колоду
@app.post("/addDeck")
def add_deck(request:Request, body:NewDeck, session:SessionDep):

    print(request)
    role = request.headers.get("role")
    if (role!="ADMIN" and role!="USER"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_uuid = request.headers.get("uuid")

    add_deck = Deck()
    add_deck.deck_name = body.deck_name
    add_deck.user_uuid = user_uuid

    session.add(add_deck)
    session.commit()





# отдельный эндпоинт для получения следующей карточки из колоды
@app.get("/next/{deck_id}")
def next_card(session: SessionDep, request:Request, deck_id:int):

    role = request.headers.get("role")
    if (role != "ADMIN" and role != "USER"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_uuid = request.headers.get("uuid")

    # вытаскиваем колоду, проверяем, что она принадлежит авторизованному пользователю
    deckSelectStatement = select(Deck).where(Deck.deck_id == deck_id)
    foundDeck = session.exec(deckSelectStatement).first()
    if (foundDeck==None):
        raise HTTPException(status_code=400, detail = "deck doesn't exists")

    if (foundDeck.user_uuid!=user_uuid):
        raise HTTPException(status = 403, detail="no permission for this id")





    statement = select(DatabaseCard).filter(DatabaseCard.due<datetime.now(timezone.utc) and DatabaseCard.deck == deck_id)
    next_card = session.exec(statement).first()
    if (next_card == None):
        answer = BackendAnswerCard()
        answer.back_content = None
        answer.front_content = None
        answer.card_id = None
        return answer
    else:
        answer = BackendAnswerCard()
        answer.back_content = next_card.back_content
        answer.front_content = next_card.front_content
        answer.card_id = next_card.card_id
        return answer




#карточка просмотрена и оценена. Эндпоинт возвращает следующую карточку, если она есть

#@app.post("/api/tools/cards/repetition")
@app.post("/repetition")
def view_cards(requestBody:RatedCard, session: SessionDep, request:Request):
    role = request.headers.get("role")
    if (role != "ADMIN" and role != "USER"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user_uuid = request.headers.get("uuid")

    # вытаскиваем колоду, проверяем, что она принадлежит авторизованному пользователю
    deckSelectStatement = select(Deck).where(Deck.deck_id == requestBody.deck_id)
    foundDeck = session.exec(deckSelectStatement).first()
    if (foundDeck == None):
        raise HTTPException(status_code=400, detail="deck doesn't exists")

    if (foundDeck.user_uuid != user_uuid):
        raise HTTPException(status=403, detail="no permission for this id")




    #получаем карточку по id
    dbCard = session.get(DatabaseCard, requestBody.card_id)





    # кормим карту алгоритму и сохраняем изменения в базу
    dbCard = convertDbEntityToFsrsCardAndMakeReview(dbCard, requestBody.rating)

    session.add(dbCard)
    session.commit()
















#@app.post("/api/tools/cards/add")
@app.post("/addCard")
def add_card(requestBody:NewCard, session: SessionDep, request:Request):
    role = request.headers.get("role")
    user_uuid = request.headers.get("uuid")
    if (role != "ADMIN" and role != "USER"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # вытаскиваем колоду, проверяем, что она принадлежит авторизованному пользователю
    deckSelectStatement = select(Deck).where(Deck.deck_id == requestBody.deck_id)
    foundDeck = session.exec(deckSelectStatement).first()
    if (foundDeck == None):
        raise HTTPException(status_code=400, detail="deck doesn't exists")

    if (foundDeck.user_uuid != user_uuid):
        raise HTTPException(status=403, detail="no permission for this id")









    scheduler = Scheduler()
    # создаем дефолтную карту
    card = Card()
    rating = Rating.Again

    print(card)

    card, review_log = scheduler.review_card(card, rating)

    dbCard = convertFsrsEntityToDbEntity(card, requestBody)

    session.add(dbCard)

    session.commit()

    if (requestBody.with_reversed):
        dbCardReversed = convertFsrsEntityToDbEntity(card, requestBody, reversed = True)

        session.add(dbCardReversed)

        session.commit()


if __name__=="__main__":
    print("hello")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")





















