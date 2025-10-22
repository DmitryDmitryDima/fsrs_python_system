from fastapi import FastAPI, Depends
from pydantic import BaseModel
from fsrs import Scheduler, Card, Rating, ReviewLog, State
from datetime import datetime, timezone
from sqlmodel import Field, Session, SQLModel, create_engine, select, Column, DateTime

from typing import Annotated, Optional

import uvicorn


app = FastAPI()


# сущность для фронтенд ответа при просмотре карточек
class RatedCard(BaseModel):
    card_id: int
    rating: str

# сущность для бэкенд ответа
class BackendAnswerCard(BaseModel):
    card_id: Optional[int] = None
    front_content: Optional[str] = None
    back_content: Optional[str] = None



class NewCard(BaseModel):
    front_content: str
    back_content: str
    with_reversed: bool





# сущность для таблицы
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



def convertFsrsEntityToDbEntity(fsrsCard:Card, front_content:str, back_content:str):
    databaseCard = DatabaseCard()
    #databaseCard.card_id = fsrsCard.card_id
    databaseCard.state = fsrsCard.state.value
    databaseCard.step = fsrsCard.step
    databaseCard.stability = fsrsCard.stability
    databaseCard.difficulty = fsrsCard.difficulty


    # аккуратнее со временем
    databaseCard.due = fsrsCard.due
    databaseCard.last_review = fsrsCard.last_review


    databaseCard.front_content = front_content
    databaseCard.back_content = back_content
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










#sqlite_file_name = "database.db"
#sqlite_url = f"sqlite:///{sqlite_file_name}"

# postgres - имя пользователя
# 123 - пароль
# localhost:5432/postgres - адрес базы данных с таблицами
postgres_url = "postgresql://postgres:123@localhost:5432/postgres"

#connect_args = {"check_same_thread": False}
#engine = create_engine(sqlite_url, connect_args=connect_args)
engine = create_engine(postgres_url)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

create_db_and_tables()

















# отдельный эндпоинт для получения следующей карточки
@app.get("/api/tools/cards/next")
def next_card(session: SessionDep):
    statement = select(DatabaseCard).filter(DatabaseCard.due<datetime.now(timezone.utc))
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
@app.post("/api/tools/cards/repetition")
def view_cards(requestBody:RatedCard, session: SessionDep):




    #получаем карточку по id
    dbCard = session.get(DatabaseCard, requestBody.card_id)

    print(dbCard)



    # кормим карту алгоритму и сохраняем изменения в базу
    dbCard = convertDbEntityToFsrsCardAndMakeReview(dbCard, requestBody.rating)

    session.add(dbCard)
    session.commit()

    # далее посылаем следующего кандидата

    statement = select(DatabaseCard).filter(DatabaseCard.due < datetime.now(timezone.utc))
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













@app.post("/api/tools/cards/add")
def add_card(requestBody:NewCard, session: SessionDep):
    scheduler = Scheduler()
    # создаем дефолтную карту
    card = Card()
    rating = Rating.Again

    print(card)

    card, review_log = scheduler.review_card(card, rating)

    dbCard = convertFsrsEntityToDbEntity(card, requestBody.front_content, requestBody.back_content)

    session.add(dbCard)

    session.commit()

    if (requestBody.with_reversed):
        dbCardReversed = convertFsrsEntityToDbEntity(card, requestBody.back_content, requestBody.front_content)

        session.add(dbCardReversed)

        session.commit()


if __name__=="__main__":
    print("hello")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")





















