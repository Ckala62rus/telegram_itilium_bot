import asyncio
import logging.config

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

from utils.logger_project import logging_config

# Загружаем настройки логирования из словаря `logging_config`
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)


from middleware.db_middleware import (
    ExecuteTimeHandlerMiddleware,
)

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


async def main():
    logger.debug('start application')
    # cron scheduler apscheduler
    # scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # scheduler.add_job(scheduler_tasks.every_minutes, trigger='interval', seconds=60, kwargs={'bot': bot})
    # scheduler.start()

    logger.debug('init middlewares')
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
    except KeyboardInterrupt as k:
        logger.error("KeyboardInterrupt exception")
        logger.exception(k)
    except Exception as e:
        logger.error("Some exception")
        logger.exception(e)
    finally:
        logger.debug("close db connection")
        # await db.close()
        logger.info("application was stopped.")


if __name__ == "__main__":
    asyncio.run(main())
