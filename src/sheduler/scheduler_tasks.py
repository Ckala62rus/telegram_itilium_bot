from aiogram import Bot
from utils.logger_project import setup_logger

logger = setup_logger(__name__)


async def every_minutes(bot: Bot):
    await bot.send_message(chat_id=123456789, text="Я работаю каждую минуту")
