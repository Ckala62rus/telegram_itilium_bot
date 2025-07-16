import logging
import asyncio
from typing import Optional, Any, Dict
import httpx
from httpx import AsyncClient, Timeout
import json as jsonlib

from config.configuration import settings

logger = logging.getLogger(__name__)


class HTTPClientManager:
    """Singleton HTTP клиент с connection pooling"""
    
    _instance: Optional['HTTPClientManager'] = None
    _client: Optional[AsyncClient] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_client(self) -> AsyncClient:
        """Получает или создает HTTP клиент"""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client
    
    async def _create_client(self) -> AsyncClient:
        """Создает новый HTTP клиент с оптимизированными настройками"""
        timeout = Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=5.0
        )
        
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=30.0
        )
        
        client = AsyncClient(
            timeout=timeout,
            limits=limits,
            headers={
                "User-Agent": "TelegramBot/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
        )
        
        logger.info("HTTP клиент создан с оптимизированными настройками")
        return client
    
    async def close(self):
        """Закрывает HTTP клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP клиент закрыт")
    
    async def __aenter__(self):
        return await self.get_client()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Не закрываем клиент здесь, так как он singleton
        pass


# Глобальный экземпляр менеджера HTTP клиентов
http_client_manager = HTTPClientManager()


async def get_http_client() -> AsyncClient:
    """Получает HTTP клиент"""
    return await http_client_manager.get_client()


async def close_http_client():
    """Закрывает HTTP клиент (вызывать при завершении приложения)"""
    await http_client_manager.close() 


def _format_dict(d: Any) -> str:
    if d is None:
        return "None"
    try:
        return jsonlib.dumps(d, ensure_ascii=False, indent=2)
    except Exception:
        return str(d)

async def log_and_request(
    method: str,
    url: str,
    *,
    params: Any = None,
    data: Any = None,
    json: Any = None,
    headers: Optional[Dict[str, Any]] = None,
    **kwargs
) -> httpx.Response:
    """
    Логирует и выполняет HTTP-запрос через общий клиент.
    :param method: HTTP-метод (GET, POST, ...)
    :param url: URL запроса
    :param params: Query параметры
    :param data: Тело запроса (form)
    :param json: Тело запроса (json)
    :param headers: Заголовки (дополнительно к дефолтным)
    :param kwargs: Остальные параметры httpx
    :return: httpx.Response
    """
    logger.info("\n[HTTP REQUEST] %s %s\nParams: %s\nData: %s\nJSON: %s\nHeaders: %s",
        method.upper(), url,
        _format_dict(params),
        _format_dict(data),
        _format_dict(json),
        _format_dict(headers)
    )
    client = await get_http_client()
    response = await client.request(
        method=method,
        url=url,
        params=params,
        data=data,
        json=json,
        headers=headers,
        **kwargs
    )
    # Логируем ответ
    resp_body = None
    try:
        resp_body = response.text
    except Exception:
        resp_body = str(response.content)
    max_len = 500
    resp_body_short = (resp_body[:max_len] + ("..." if len(resp_body) > max_len else "")) if resp_body else ""
    logger.info(
        "[HTTP RESPONSE] %s %s | Status: %s\nHeaders: %s\nBody: %s",
        method.upper(), url, response.status_code,
        _format_dict(dict(response.headers)),
        resp_body_short
    )
    return response

# Пример использования:
# response = await log_and_request(
#     "POST",
#     "https://api.example.com/v1/resource",
#     params={"id": 123},
#     json={"name": "test"},
#     headers={"Authorization": "Bearer ..."}
# ) 