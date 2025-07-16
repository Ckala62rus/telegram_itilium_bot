import logging
import sys
import redis.asyncio as redis
from redis.exceptions import AuthenticationError
from config.configuration import settings

logger = logging.getLogger(__name__)

class AsyncRedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance

    async def get_client(self):
        if self._client is None:
            try:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWORD,
                    db=settings.REDIS_DATABASE,
                    decode_responses=True,
                )
                await self._client.ping()
                logger.info("Connected to Redis successfully.")
            except TimeoutError:
                logger.error('❌ Ошибка. Подключение к базе данных Redis')
                sys.exit()
            except AuthenticationError:
                logger.error('❌ Ошибка. Не удалось выполнить аутентификацию соединения Redis с базой данных.')
                sys.exit()
            except Exception as e:
                logger.error(f'❌ Ошибка. Неверное соединение с базой данных Redis: {e}')
                sys.exit()
        return self._client

# Экземпляр singleton-клиента
async_redis_client = AsyncRedisClient()
