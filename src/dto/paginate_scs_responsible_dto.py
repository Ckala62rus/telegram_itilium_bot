import json

from redis import Redis


class PaginateResponsibleScsDTO:
    def __init__(
            self,
            redis: Redis,
            user_id: int,
    ):
        self.r: Redis = redis
        self.user_id: int = user_id
        self.scs: list = list()

    def set_cache_responsible_scs(self, scs: list) -> None:
        """
        Устанавливаем кэш данных по заявкам конкретного пользователя в Redis
        """
        # кешируем результат
        # Добавление элемента в начало списка
        for sc in scs:
            self.r.rpush(f"responsible:{str(self.user_id)}", json.dumps(sc))

        # Указываем срок хранения для списка в 60 секунды
        self.r.expire(f"responsible:{str(self.user_id)}", 60)

    def get_cache_responsible_scs(self) -> list:
        """
        Получаем кэш данных по заявкам конкретного пользователя в Redis
        """
        # извлекаем из редиса
        return self.r.lrange(f"responsible:{str(self.user_id)}", 0, -1)
