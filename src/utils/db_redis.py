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
                # Создаем подключение к Redis с опциональным паролем
                redis_config = {
                    'host': settings.REDIS_HOST,
                    'port': settings.REDIS_PORT,
                    'db': settings.REDIS_DATABASE,
                    'decode_responses': True,
                }
                
                # Добавляем пароль только если он установлен
                if settings.REDIS_PASSWORD:
                    redis_config['password'] = settings.REDIS_PASSWORD
                
                self._client = redis.Redis(**redis_config)
                await self._client.ping()
                logger.info("Connected to Redis successfully.")
            except TimeoutError:
                logger.warning('⚠️ Предупреждение. Не удалось подключиться к Redis (таймаут). Бот будет работать без кэширования.')
                self._client = None
            except AuthenticationError:
                logger.warning('⚠️ Предупреждение. Ошибка аутентификации Redis. Бот будет работать без кэширования.')
                self._client = None
            except Exception as e:
                logger.warning(f'⚠️ Предупреждение. Ошибка подключения к Redis: {e}. Бот будет работать без кэширования.')
                self._client = None
        return self._client

# Экземпляр singleton-клиента
async_redis_client = AsyncRedisClient()
