import json
import logging

import httpx
from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserButtonText
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
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


@new_user_router.message(StateFilter('*'), F.text.casefold() == str(UserButtonText.CANCEL))
async def cancel_fsm_handler(message: types.Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer(
        str(UserButtonText.ACTIONS_CANCELED),
        reply_markup=types.ReplyKeyboardRemove()
    )


@new_user_router.message(Command("menu"))
@new_user_router.message(F.text == str(UserButtonText.MENU))
async def get_all_scs_types_handler_reply_markup(message: types.Message):
    """
    Метод, определяющий возможность выбора "типов" заявок, доступных пользователю. Список "типов" заявок
    выводится в зависимоти от типа пользователя (сотрудник IT/нет)
    """

    logger.debug("command or message -> menu")

    # await message.delete()
    # remove_keyboard = await message.answer(text="...", reply_markup=types.ReplyKeyboardRemove())
    # await remove_keyboard.delete()

    # (todo нужно это или нет?) добавляем пользователя в текщий список пользоватлей бота и проверяем, явлется ли он ключевым

    logger.debug("Отправляем inline кнопки меню")
    await message.answer("Выберите необходимый пункт меню:", reply_markup=USER_MENU_KEYBOARD)
    await message.answer(
        text=str(UserButtonText.CHOOSE_MENY),
        # reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    )

    # сохраняем идентификатор собщения для послдующего удаления при зваершении сессии
    # current_bot_users.add_current_session_mes_id_to_list(message.from_user.id, message.message_id)
    # current_bot_users.set_current_message_state(message.from_user.id, 'service_call')


@new_user_router.callback_query(StateFilter(None), F.data.startswith("crate_new_issue"))
async def start_command(callback: types.CallbackQuery, state: FSMContext):
    logger.debug("Perform callback command create_new_issue and get cancel button")
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        text="Введите описание обращения",
        reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    )

    await state.set_state(CreateNewIssue.description)


@new_user_router.message(CreateNewIssue.description, F.text)
async def set_description_for_issue(
        message: types.Message,
        state: FSMContext
):
    logger.debug("enter description for new issue")

    if len(message.text) == 0:
        await message.answer("Вы ввели пустое описание. Введите описание заного или отмените все действия")
        return

    await state.update_data(description=message.text)

    logger.debug(f"get user information from itilium by telegram id {message.from_user.id}")
    user_data_from_itilium: dict | None = await ItiliumBaseApi.get_employee_data_by_identifier(message)

    if user_data_from_itilium is None:
        logger.debug("user not found in Itilium")
        await state.clear()
        await message.answer(
            text="Не удалось найти вас в системе ITILIUM",
            reply_markup=types.ReplyKeyboardRemove()
        )

    # send date to itilium api for create issue
    response: Response = await ItiliumBaseApi.create_new_sc({
        "UUID": user_data_from_itilium["UUID"],
        "Description": message.text,
        "shortDescription": message.text,
    })

    logger.debug(f"{response.status_code} | {response.text}")

    if response.status_code == httpx.codes.OK:
        await message.answer(f"Ваша завка успешно создана!\n\r{json.loads(response.text)}")
    else:
        logger.debug(f"{response.text}")
        await message.answer(f"Не удалось создать заявку. Ошибка сервера {response.text}\n\rПовотрите попытку позже")

    await state.clear()


@new_user_router.callback_query(F.data.startswith("accept$"))
async def btn_accept(callback: types.CallbackQuery):
    """
    Обработчик кнопки "Согласовать"
    Переводит согласование в статус "Согласовано"
    Формирует сообщение о выполнении действия, либо об ошибке.
    Формат текста по нажатию на кнопку согласовать 'accept$000001844'
    """
    try:
        logger.debug(f"{callback.data}")
        await ItiliumBaseApi.accept_callback_handler(callback)
        await callback.answer()
        await callback.message.answer("Согласовано")
    except Exception as e:
        logger.error(e)
        await callback.answer("Во время согласования, произошла ошибка. Обратитесь к администратору")

    await callback.answer()


@new_user_router.callback_query(F.data.startswith("reject$"))
async def btn_reject(callback: types.CallbackQuery):
    """
    Обработчик кнопки "Отклонить"
    Переводит согласование в статус "Отклонить"
    Формирует сообщение о выполнении действия, либо об ошибке.
    Формат текста по нажатию на кнопку согласовать 'reject$000001844'
    """
    try:
        logger.debug(f"{callback.data}")
        await ItiliumBaseApi.reject_callback_handler(callback)
        await callback.answer()
        await callback.message.answer("Отклонено")
    except Exception as e:
        logger.error(e)
        await callback.answer("Во время согласования, произошла ошибка. Обратитесь к администратору")


@new_user_router.message(F.text)
async def magic_filter(message: types.Message):
    await message.answer(text="Я не понимаю Вашей команды (((")
