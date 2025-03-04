import logging
import sys

import redis
from redis import Redis, AuthenticationError

from config.configuration import settings

logger = logging.getLogger(__name__)


# class RedisCli(Redis):
class RedisCli:
    r: Redis = None

    def __init__(self):
        logger.info("Initializing Redis Cli")
        logger.debug(f"settings.REDIS_HOST: {settings.REDIS_HOST}")

        # super(RedisCli, self).__init__(
        #     host=settings.REDIS_HOST,
        #     port=settings.REDIS_PORT,
        #     # password=settings.REDIS_PASSWORD,
        #     db=settings.REDIS_DATABASE,
        #     socket_timeout=settings.REDIS_TIMEOUT,
        #     decode_responses=True,  # Кодировка utf-8
        # )

        self.r = redis.Redis(
            host="redis_itilium",
            port=6379,
            # password=123123,
            db=0,
            decode_responses=True,  # Результат сразу конвертируем в строку из байт
        )

        res = self.r.ping()
        print(123)

    async def open(self):
        """
        Инициализация

        :return:
        """
        try:
            await self.r.ping()
        except TimeoutError:
            logger.error('❌ Ошибка. Подключение к базе данных Redis')
            sys.exit()
        except AuthenticationError:
            logger.error('❌ Ошибка. Не удалось выполнить аутентификацию соединения Redis с базой данных.')
            sys.exit()
        except Exception as e:
            logger.error('❌ Ошибка. Неверное соединение с базой данных Redis {}', e)
            sys.exit()

    async def delete_prefix(self, prefix: str, exclude: str | list = None):
        """
        Удалить все ключи, указанные в предыдущем разделе.

        :param prefix:
        :param exclude:
        :return:
        """
        keys = []
        for key in self.r.scan_iter(match=f'{prefix}*'):
            if isinstance(exclude, str):
                if key != exclude:
                    keys.append(key)
            elif isinstance(exclude, list):
                if key not in exclude:
                    keys.append(key)
            else:
                keys.append(key)
        for key in keys:
            await self.r.delete(key)


def get_redis_db():
    """
    Возвращаем экземпляр Redis, но проверяем, есть ли соединение с Redis
    """
    r = redis.Redis(
        host="redis_itilium",
        port=6379,
        # password=123123,
        db=0,
        decode_responses=True,  # Результат сразу конвертируем в строку из байт
    )

    try:
        r.ping()
    except TimeoutError:
        logger.error('❌ Ошибка. Подключение к базе данных Redis')
        sys.exit()
    except AuthenticationError:
        logger.error('❌ Ошибка. Не удалось выполнить аутентификацию соединения Redis с базой данных.')
        sys.exit()
    except Exception as e:
        logger.error('❌ Ошибка. Неверное соединение с базой данных Redis {}', e)
        sys.exit()

    return r


# Создание redis экземпляра
# redis_client = RedisCli()
redis_client = get_redis_db()
