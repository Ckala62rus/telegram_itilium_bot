from aiogram import Bot


async def every_minutes(bot: Bot):
    await bot.send_message(chat_id=123456789, text="Я работаю каждую минуту")
