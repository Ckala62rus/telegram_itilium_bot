import logging
import json
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from functools import wraps

from utils.db_redis import async_redis_client

logger = logging.getLogger(__name__)


class CacheManager:
    """Менеджер кэширования для оптимизации запросов"""
    
    def __init__(self):
        self.default_ttl = 300  # 5 минут по умолчанию
    
    async def get(self, key: str) -> Optional[Any]:
        """Получает данные из кэша"""
        try:
            redis_client = await async_redis_client.get_client()
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения из кэша {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Сохраняет данные в кэш"""
        try:
            redis_client = await async_redis_client.get_client()
            ttl = ttl or self.default_ttl
            await redis_client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Удаляет данные из кэша"""
        try:
            redis_client = await async_redis_client.get_client()
            await redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Проверяет существование ключа в кэше"""
        try:
            redis_client = await async_redis_client.get_client()
            return await redis_client.exists(key)
        except Exception as e:
            logger.error(f"Ошибка проверки кэша {key}: {e}")
            return False
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Генерирует ключ кэша"""
        key_parts = [prefix]
        
        # Добавляем позиционные аргументы
        for arg in args:
            key_parts.append(str(arg))
        
        # Добавляем именованные аргументы
        for key, value in sorted(kwargs.items()):
            key_parts.append(f"{key}:{value}")
        
        return ":".join(key_parts)


# Глобальный экземпляр менеджера кэша
cache_manager = CacheManager()


def cache_result(prefix: str, ttl: int = 300):
    """Декоратор для кэширования результатов функций"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = cache_manager.generate_key(prefix, *args, **kwargs)
            
            # Пытаемся получить из кэша
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Кэш HIT для {cache_key}")
                return cached_result
            
            # Выполняем функцию и кэшируем результат
            logger.debug(f"Кэш MISS для {cache_key}")
            result = await func(*args, **kwargs)
            
            if result is not None:
                await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


# Специализированные функции кэширования
async def cache_user_data(user_id: int, data: Dict[str, Any], ttl: int = 600):
    """Кэширует данные пользователя"""
    key = f"user:{user_id}:data"
    return await cache_manager.set(key, data, ttl)


async def get_cached_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Получает кэшированные данные пользователя"""
    key = f"user:{user_id}:data"
    return await cache_manager.get(key)


async def invalidate_user_cache(user_id: int):
    """Инвалидирует кэш пользователя"""
    key = f"user:{user_id}:data"
    await cache_manager.delete(key)


async def cache_service_calls(user_id: int, calls: list, ttl: int = 300):
    """Кэширует список заявок пользователя"""
    key = f"user:{user_id}:service_calls"
    return await cache_manager.set(key, calls, ttl)


async def get_cached_service_calls(user_id: int) -> Optional[list]:
    """Получает кэшированный список заявок пользователя"""
    key = f"user:{user_id}:service_calls"
    return await cache_manager.get(key) 