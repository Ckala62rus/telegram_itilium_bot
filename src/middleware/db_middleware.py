import logging
from typing import (
    Callable,
    Dict,
    Any,
    Awaitable,
)
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from database.orm_query_command import add_user_command
from database.orm_query_user import get_user_by_telegram_id

logger = logging.getLogger(__name__)


class DatabaseSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker) -> None:
        self.db_session = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with self.db_session as session:
            data['db_session'] = session
            logger.debug('middleware database session')
            return await handler(event, data)


class SaveInputCommandMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        pass

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        session: AsyncSession = data['db_session']

        logger.debug('middleware save input command')

        if event.callback_query is not None:
            callback: CallbackQuery = event.callback_query

            logger.debug(f"callback query: {callback.data}")
            return await handler(event, data)

        if event.message is not None:
            text = event.message.text
            telegram_user_id = event.message.chat.id

            if text is not None:
                user = await get_user_by_telegram_id(session, telegram_user_id)

                if user is not None:
                    await add_user_command(session, {
                        "command": text,
                        "user_id": user.id,
                    })

                    await session.commit()

        return await handler(event, data)
