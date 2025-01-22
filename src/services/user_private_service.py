import logging

from aiogram import types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot_enums.user_enums import UserText, UserButtonText
from kbds.reply import get_keyboard


logger = logging.getLogger(__name__)


async def base_start_handler(message: types.Message) -> None:
    """
    Базовый обработчик начала работы с ботом. Отсылает собщение-справку по работе с ботом, а также происходит
    заполнение полей tlgrmChatId и telegram в классе "сотрудник" для нормальной работы бота
    """

    logger.debug("base_start_handler")

    # Отправка сообщения для начального ознакомления
    await message.answer(
        text=str(UserText.START_GREETINGS)
    )

    await message.answer(
        text=str(UserText.GO_TO_MAIN_MENU),
        reply_markup=get_keyboard(*[
            str(UserButtonText.MENU)
        ])
    )
