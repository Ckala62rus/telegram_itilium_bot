import asyncio
import logging.config
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommandScopeAllPrivateChats
from sqlalchemy import text

from config.configuration import settings
from database.db import session_factory
from common.bot_cmds_list import private
from database.session_db_manager import db_session
from handlers.user_private import user_private_router
from handlers.user_proup import user_group_router
from handlers.admin_private import admin_router
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from sheduler import scheduler_tasks

from utils.logger_project import logging_config

# Загружаем настройки логирования из словаря `logging_config`
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)


from middleware.db_middleware import (
    DatabaseSessionMiddleware,
    SaveInputCommandMiddleware,
)

# default file name for find '.env'
# load_dotenv(find_dotenv())

bot = Bot(token=settings.BOT_TOKEN)
bot.my_admins_list = []
dp = Dispatcher()

logger.debug('init routers')
# dp.include_router(user_group_router)
dp.include_router(user_private_router)
dp.include_router(admin_router)
logger.debug('success init routers')

ALLOWED_UPDATES = ['message', 'edited_message', 'callback_query']


async def main():
    logger.debug('start application')
    # cron scheduler apscheduler
    # scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # scheduler.add_job(scheduler_tasks.every_minutes, trigger='interval', seconds=60, kwargs={'bot': bot})
    # scheduler.start()

    # init database session via middleware
    db = db_session.session_factory()

    logger.debug('init middlewares')
    dp.update.middleware(DatabaseSessionMiddleware(session_pool=db))
    dp.update.middleware(SaveInputCommandMiddleware())
    logger.debug('end init middlewares')
    logger.critical('Test critical error main app')
    async with session_factory() as session_pool:
        logger.debug('check database connection')
        try:
            await session_pool.execute(text("SELECT 1"))  # check database connection
            logger.debug('database connection success')
        except Exception as e:
            logger.exception(e)
            logger.error('❌ Error to connect database')
            sys.exit()

    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands(scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(
        commands=private,
        scope=BotCommandScopeAllPrivateChats()
    )
    logger.debug('start polling')
    # await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt as k:
        logger.info("KeyboardInterrupt exception")
        logger.exception(k)
    except Exception as e:
        logger.info("Some exception")
        logger.exception(e)
    finally:
        logger.debug("close db connection")
        await db.close()
        logger.info("application was stopped.")


if __name__ == "__main__":
    asyncio.run(main())
