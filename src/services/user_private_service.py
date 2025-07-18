import json
import logging

from aiogram import types
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, Message
from httpx import Response

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserText, UserButtonText
from dto.paginate_scs_dto import PaginateScsDTO
from dto.paginate_scs_responsible_dto import PaginateResponsibleScsDTO
from kbds.reply import get_keyboard
from utils.message_templates import MessageTemplates

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


async def paginate_scs_logic(
    callback: types.CallbackQuery,
    paginate_dto: PaginateScsDTO,
) -> dict:
    user = await ItiliumBaseApi.get_employee_data_by_identifier(callback)

    if user is None:
        return {}

    logger.debug(f"user: {user['servicecalls']}")

    await callback.answer()
    send_message_for_search = await callback.message.answer(MessageTemplates.LOADING_REQUESTS)

    my_scs: list = user['servicecalls']

    if not my_scs:
        await callback.answer()
        await send_message_for_search.delete()
        await callback.message.answer(MessageTemplates.NO_CREATED_ISSUES)
        return {}

    results = await ItiliumBaseApi.get_task_for_async_find_sc_by_id(scs=my_scs, callback=callback)

    await paginate_dto.set_cache_scs(results)

    return {"send_message_for_search": send_message_for_search}


async def paginate_responsible_scs_logic(
    callback: types.CallbackQuery,
    paginate_dto: PaginateResponsibleScsDTO,
) -> dict:
    response: Response = await ItiliumBaseApi.scs_responsibility_tasks(callback.from_user.id)

    my_scs = json.loads(response.text)

    await callback.answer()
    send_message_for_search = await callback.message.answer(MessageTemplates.LOADING_REQUESTS)

    if not my_scs:
        await callback.answer()
        await send_message_for_search.delete()
        await callback.message.answer(MessageTemplates.NO_RESPONSIBLE_ISSUES)
        return {}

    results = await ItiliumBaseApi.get_task_for_async_find_sc_by_id(scs=my_scs, callback=callback)

    await paginate_dto.set_cache_responsible_scs(results)

    return {"send_message_for_search": send_message_for_search}
