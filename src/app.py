import asyncio
import logging.config
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeAllPrivateChats

from config.configuration import settings
from common.bot_cmds_list import private
from dialogs import custom_setup_dialogs
from handlers.group_handler import user_group_router
from handlers.new_user_handler import new_user_router
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from sheduler import scheduler_tasks

from utils.logger_project import setup_logger, LOG_LEVEL_INFO, LOG_LEVEL_DEBUG
from utils.http_client import close_http_client
from utils.db_redis import async_redis_client

logger = logging.getLogger(__name__)


from middleware.db_middleware import (
    ExecuteTimeHandlerMiddleware,
)
from middleware.user_access_middleware import UserAccessMiddleware

storage = MemoryStorage()
bot = Bot(token=settings.BOT_TOKEN)
bot.my_admins_list = []
dp = Dispatcher(storage=storage)


# Aiogram dialog registration
custom_setup_dialogs(dp)


logger.debug('init routers')
dp.include_router(user_group_router)
dp.include_router(new_user_router)
logger.debug('success init routers')

ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']


async def shutdown(signal, loop):
    """Корректное завершение приложения"""
    logger.info(f"Получен сигнал {signal.name}...")
    
    # Останавливаем бота
    await bot.session.close()
    
    # Закрываем HTTP клиент
    await close_http_client()
    
    # Закрываем Redis соединение
    try:
        redis_client = await async_redis_client.get_client()
        await redis_client.close()
        logger.info("Redis соединение закрыто")
    except Exception as e:
        logger.error(f"Ошибка при закрытии Redis: {e}")
    
    # Останавливаем event loop
    loop.stop()
    logger.info("Приложение корректно завершено")


async def main():
    logger.debug('start application')
    
    # Настройка обработчиков сигналов для корректного завершения
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s, loop))
        )
    
    # cron scheduler apscheduler
    # scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # scheduler.add_job(scheduler_tasks.every_minutes, trigger='interval', seconds=60, kwargs={'bot': bot})
    # scheduler.start()

    logger.debug('init middlewares')
    access_middleware = UserAccessMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)
    dp.update.middleware(ExecuteTimeHandlerMiddleware())
    logger.debug('end init middlewares')

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(
        commands=private,
        scope=BotCommandScopeAllPrivateChats()
    )
    logger.debug('start polling')
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error("Критическая ошибка в приложении")
        logger.exception(e)
        sys.exit(1)
    finally:
        logger.info("Приложение остановлено")


if __name__ == "__main__":
    setup_logger(level=LOG_LEVEL_DEBUG)  # INFO по умолчанию, можно изменить на LOG_LEVEL_DEBUG при необходимости
    asyncio.run(main())
