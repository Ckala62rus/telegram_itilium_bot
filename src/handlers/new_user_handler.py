import logging

from aiogram import types, Router, F
from aiogram.filters import CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot_enums.user_enums import UserButtonText
from filters.chat_types import ChatTypeFilter
from kbds.user_kbds import USER_MENU_KEYBOARD
from services.user_private_service import base_start_handler

new_user_router = Router()
new_user_router.message.filter(ChatTypeFilter(['private']))

logger = logging.getLogger(__name__)


@new_user_router.message(CommandStart())
async def start_command(message: types.Message):
    """
    Обработчик команды /start, инициирующей работу бота, при инициализации работы с ботом. Происходит вызов
    общего обработчика начала работы с ботом
    """

    logger.debug("Command start")
    logger.info(message.from_user.id)

    await base_start_handler(message)

@new_user_router.message(F.text == str(UserButtonText.MENU))
async def get_all_scs_types_handler_reply_markup(message: types.Message):
    """
    Метод, определяющий возможность выбора "типов" заявок, доступных пользователю. Список "типов" заявок
    выводится в зависимоти от типа пользователя (сотрудник IT/нет)
    """

    await message.delete()
    remove_keyboard = await message.answer(text="...", reply_markup=types.ReplyKeyboardRemove())
    await remove_keyboard.delete()

    # добавляем пользователя в текщий список пользоватлей бота и проверяем, явлется ли он ключевым
    await message.answer(
        text=str(UserButtonText.CHOOSE_MENY),
        reply_markup=USER_MENU_KEYBOARD
    )
