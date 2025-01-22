import logging
import os
from functools import lru_cache

from dotenv import (
    load_dotenv,
    find_dotenv
)

from utils.path_conf import BasePath

# default file name for find '.env'
load_dotenv(find_dotenv(BasePath.joinpath('.env')))
logger = logging.getLogger(__name__)


class Settings:

    # POSTGRES
    POSTGRES_USER: str = os.getenv('POSTGRES_USER')
    POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD')
    POSTGRES_DB: str = os.getenv('POSTGRES_DB')
    POSTGRES_PORT: str = os.getenv('POSTGRES_PORT')
    POSTGRES_HOST: str = os.getenv('POSTGRES_HOST')
    SQLALCHEMY_DATABASE_URL: str = f'postgresql+psycopg://postgres:postgres@{os.getenv('POSTGRES_HOST')}:5432/alch'
    SQLALCHEMY_DATABASE_URL_FOR_ALEMBIC: str = f'postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}'

    # BOT_TOKEN
    BOT_TOKEN: str = os.getenv('TOKEN')

    # LARAVEL_BACKEND
    LARAVEL_API_URL: str = os.getenv('LARAVEL_API_URL')


# Декоратор lru_cache для хэширования конфига, что бы при следующих обращениях брался его кеш
@lru_cache
def _get_settings() -> Settings:
    """
    Load settings from env
    :return:
    """
    return Settings()


# Создание экземпляра конфигурационного класса
settings = _get_settings()
