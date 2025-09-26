import logging
import os
from functools import lru_cache
from typing import Optional

from dotenv import (
    load_dotenv,
    find_dotenv
)

from utils.path_conf import BasePath

# default file name for find '.env'
load_dotenv(find_dotenv(BasePath.joinpath('.env')))
logger = logging.getLogger(__name__)


class Settings:
    """Настройки приложения с валидацией"""
    
    def __init__(self):
        # POSTGRES
        self.POSTGRES_USER: str = self._get_required_env('POSTGRES_USER')
        self.POSTGRES_PASSWORD: str = self._get_required_env('POSTGRES_PASSWORD')
        self.POSTGRES_DB: str = self._get_required_env('POSTGRES_DB')
        self.POSTGRES_PORT: str = self._get_required_env('POSTGRES_PORT')
        self.POSTGRES_HOST: str = self._get_required_env('POSTGRES_HOST')
        
        # BOT_TOKEN
        self.BOT_TOKEN: str = self._get_required_env('TOKEN')
        
        # ITILIUM
        self.ITILIUM_URL: str = self._get_required_env("ITILIUM_URL")
        self.ITILIUM_LOGIN: str = self._get_required_env("ITILIUM_LOGIN")
        self.ITILIUM_PASSWORD: str = self._get_required_env("ITILIUM_PASSWORD")
        
        # Redis
        self.REDIS_HOST: str = self._get_required_env("REDIS_HOST")
        self.REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
        self.REDIS_DATABASE: int = int(os.getenv("REDIS_DATABASE", "0"))
        self.REDIS_TIMEOUT: int = int(os.getenv("REDIS_TIMEOUT", "5"))
        
        # Telegram organizations ids
        self.BARS_GROUP_TELEGRAM_ID: Optional[int] = self._get_optional_int_env("BARS_GROUP_TELEGRAM_ID")
        
        # HTTP клиент настройки
        self.HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "30"))
        self.HTTP_MAX_RETRIES: int = int(os.getenv("HTTP_MAX_RETRIES", "3"))
        
        # Кэш настройки
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        self.USER_CACHE_TTL: int = int(os.getenv("USER_CACHE_TTL", "600"))
        
        # Логирование
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Валидация настроек
        self._validate_settings()
        
        # Формируем URL для базы данных
        self.SQLALCHEMY_DATABASE_URL: str = f'postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
        self.SQLALCHEMY_DATABASE_URL_FOR_ALEMBIC: str = f'postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'
    
    def _get_required_env(self, key: str) -> str:
        """Получает обязательную переменную окружения"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Обязательная переменная окружения {key} не установлена")
        return value
    
    def _get_optional_int_env(self, key: str) -> Optional[int]:
        """Получает опциональную целочисленную переменную окружения"""
        value = os.getenv(key)
        if value:
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Неверное значение для {key}: {value}, должно быть целым числом")
                return None
        return None
    
    def _validate_settings(self):
        """Валидирует настройки"""
        # Проверяем порты
        if not (1 <= self.REDIS_PORT <= 65535):
            raise ValueError(f"REDIS_PORT должен быть в диапазоне 1-65535, получено: {self.REDIS_PORT}")
        
        if not (0 <= self.REDIS_DATABASE <= 15):
            raise ValueError(f"REDIS_DATABASE должен быть в диапазоне 0-15, получено: {self.REDIS_DATABASE}")
        
        # Проверяем таймауты
        if self.REDIS_TIMEOUT <= 0:
            raise ValueError(f"REDIS_TIMEOUT должен быть положительным, получено: {self.REDIS_TIMEOUT}")
        
        if self.HTTP_TIMEOUT <= 0:
            raise ValueError(f"HTTP_TIMEOUT должен быть положительным, получено: {self.HTTP_TIMEOUT}")
        
        # Проверяем TTL кэша
        if self.CACHE_TTL <= 0:
            raise ValueError(f"CACHE_TTL должен быть положительным, получено: {self.CACHE_TTL}")
        
        if self.USER_CACHE_TTL <= 0:
            raise ValueError(f"USER_CACHE_TTL должен быть положительным, получено: {self.USER_CACHE_TTL}")
        
        logger.info("Настройки успешно загружены и валидированы")


# Декоратор lru_cache для хэширования конфига
@lru_cache
def _get_settings() -> Settings:
    """Загружает настройки из переменных окружения"""
    return Settings()


# Создание экземпляра конфигурационного класса
settings = _get_settings()
