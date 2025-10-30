import json
import logging
from utils.db_redis import async_redis_client

logger = logging.getLogger(__name__)


class PaginateMarketingSubdivisionsDTO:
    def __init__(self, user_id: int):
        self.user_id: int = user_id
        self.subdivisions: list = list()

    async def set_cache_subdivisions(self, subdivisions: list) -> None:
        """
        Устанавливаем кэш данных по подразделениям маркетинга конкретного пользователя в Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return  # Если Redis недоступен, просто пропускаем кэширование
        
        # кешируем результат
        for subdivision in subdivisions:
            await redis_client.rpush(f"marketing_subdivisions:{str(self.user_id)}", json.dumps(subdivision))

        # Указываем срок хранения для списка в 60 секунды
        await redis_client.expire(f"marketing_subdivisions:{str(self.user_id)}", 60)

    async def get_cache_subdivisions(self) -> list:
        """
        Получаем кэш данных по подразделениям маркетинга конкретного пользователя из Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return []  # Если Redis недоступен, возвращаем пустой список
        # извлекаем из редиса
        return await redis_client.lrange(f"marketing_subdivisions:{str(self.user_id)}", 0, -1)

    async def exists(self) -> bool:
        """
        Проверяем, существует ли ключ в Redis
        """
        redis_client = await async_redis_client.get_client()
        if redis_client is None:
            return False  # Если Redis недоступен, считаем что данных нет
        return await redis_client.exists(f"marketing_subdivisions:{str(self.user_id)}")





