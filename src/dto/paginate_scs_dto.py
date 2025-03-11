import json

from aiogram.methods import SendMessage
from redis import Redis


class PaginateScsDTO:
    def __init__(
            self,
            redis: Redis,
            user_id: int,
            # scs: list | None,
            # send_message_for_search: None | SendMessage,
    ):
        self.r: Redis = redis
        self.user_id: int = user_id
        self.scs: list = list()

    def set_cache_scs(self, scs: list) -> None:
        """
        Устанавливаем кэш данных по заявкам конкретного пользователя в Redis
        """
        # кешируем результат
        # Добавление элемента в начало списка
        for sc in scs:
            self.r.rpush(str(self.user_id), json.dumps(sc))

        # Указываем срок хранения для списка в 60 секунды
        self.r.expire(str(self.user_id), 60)

    def get_cache_scs(self) -> list:
        """
        Получаем кэш данных по заявкам конкретного пользователя в Redis
        """
        # извлекаем из редиса
        return self.r.lrange(str(self.user_id), 0, -1)
