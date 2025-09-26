import json
import logging
from utils.db_redis import async_redis_client

logger = logging.getLogger(__name__)


class PaginateTeamsDTO:
    def __init__(self, user_id: int, sc_number: str):
        self.user_id: int = user_id
        self.sc_number: str = sc_number
        self.teams: list = list()

    async def set_cache_teams(self, teams: list) -> None:
        """
        Устанавливаем кэш данных по подразделениям конкретного пользователя в Redis
        """
        redis_client = await async_redis_client.get_client()
        # кешируем результат
        for team in teams:
            await redis_client.rpush(f"teams:{str(self.user_id)}:{self.sc_number}", json.dumps(team))

        # Указываем срок хранения для списка в 60 секунды
        await redis_client.expire(f"teams:{str(self.user_id)}:{self.sc_number}", 60)

    async def get_cache_teams(self) -> list:
        """
        Получаем кэш данных по подразделениям конкретного пользователя из Redis
        """
        redis_client = await async_redis_client.get_client()
        # извлекаем из редиса
        return await redis_client.lrange(f"teams:{str(self.user_id)}:{self.sc_number}", 0, -1)

    async def exists(self) -> bool:
        """
        Проверяем, существует ли ключ в Redis
        """
        redis_client = await async_redis_client.get_client()
        return await redis_client.exists(f"teams:{str(self.user_id)}:{self.sc_number}")
