import json
import logging
from utils.db_redis import async_redis_client

logger = logging.getLogger(__name__)

class PaginateResponsibleScsDTO:
    def __init__(self, user_id: int):
        self.user_id: int = user_id
        self.scs: list = list()

    async def set_cache_responsible_scs(self, scs: list) -> None:
        """
        Устанавливаем кэш данных по заявкам конкретного пользователя в Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return  # Если Redis недоступен, просто пропускаем кэширование
        
        # кешируем результат
        # Добавление элемента в начало списка
        for sc in scs:
            await redis_client.rpush(f"responsible:{str(self.user_id)}", json.dumps(sc))

        # Указываем срок хранения для списка в 60 секунды
        await redis_client.expire(f"responsible:{str(self.user_id)}", 60)

    async def get_cache_responsible_scs(self) -> list:
        """
        Получаем кэш данных по заявкам конкретного пользователя из Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return []  # Если Redis недоступен, возвращаем пустой список
        # извлекаем из редиса
        return await redis_client.lrange(f"responsible:{str(self.user_id)}", 0, -1)

    async def exists(self) -> bool:
        """
        Проверяем, существует ли ключ в Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return False  # Если Redis недоступен, считаем что данных нет
        return await redis_client.exists(f"responsible:{str(self.user_id)}")
