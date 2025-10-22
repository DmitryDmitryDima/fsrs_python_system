
from fsrs import Scheduler, Card, Rating, ReviewLog
from datetime import datetime, timezone



def testFsrs():
    print("hello fsrs")

    scheduler = Scheduler()

    card = Card()
    card.card_id = 1

    rating = Rating.Hard

    # выполняем просмотр карты через объект scheduler, запихивая туда рейтинг и саму карту
    card, review_log = scheduler.review_card(card, rating)

    print(card)






    print(f"Card rated {review_log.rating} at {review_log.review_datetime}")

    # считаем, когда карта должна будет быть просмотрена.
    # Как я понял,при формировании очереди на повторение мы должны смотреть, достигнуто ли это время

    due = card.due

    # пример расчета - через сколько карта будет готова к просмотру
    time_delta = due - datetime.now(timezone.utc)

    print(f"Card due on {due}")
    print(f"Card due in {time_delta.seconds} seconds")


    # таким образом, в бд у нас должны быть все   поля card. Общий для всех сущностей - card_id


testFsrs()



