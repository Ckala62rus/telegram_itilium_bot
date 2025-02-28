import asyncio
import json
import logging
import time

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from httpx import Response

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserButtonText
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue, CreateComment, SearchSC
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
from kbds.user_kbds import USER_MENU_KEYBOARD
from services.user_private_service import base_start_handler
from utils.helpers import Helpers

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
        await message.answer(
            "действия отменены",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    await state.clear()
    await message.answer(
        str(UserButtonText.ACTIONS_CANCELED),
        reply_markup=types.ReplyKeyboardRemove()
    )


@new_user_router.message(Command("menu"))
@new_user_router.message(F.text == str(UserButtonText.MENU))
async def handler_menu_command(
        message: types.Message,
        state: FSMContext
):
    """
    Метод, определяющий возможность выбора "типов" заявок, доступных пользователю. Список "типов" заявок
    выводится в зависимоти от типа пользователя (сотрудник IT/нет)
    """

    await message.delete()
    await state.clear()
    logger.debug("command or message -> menu")

    # await message.delete()
    # remove_keyboard = await message.answer(text="...", reply_markup=types.ReplyKeyboardRemove())
    # await remove_keyboard.delete()

    # (todo нужно это или нет?) добавляем пользователя в текщий список пользоватлей бота и проверяем, явлется ли он ключевым

    logger.debug("Отправляем inline кнопки меню")
    await message.answer("Выберите необходимый пункт меню:", reply_markup=USER_MENU_KEYBOARD)
    # await message.answer(
    #     text=str(UserButtonText.CHOOSE_MENY),
    #     # reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    # )

    # сохраняем идентификатор собщения для послдующего удаления при зваершении сессии
    # current_bot_users.add_current_session_mes_id_to_list(message.from_user.id, message.message_id)
    # current_bot_users.set_current_message_state(message.from_user.id, 'service_call')


@new_user_router.callback_query(StateFilter(None), F.data.startswith("crate_new_issue"))
async def crate_new_issue_command(callback: types.CallbackQuery, state: FSMContext):
    """
    Метод инициирует создание нового обращение с FSM состоянием.
    (Обращение создается как с текстом, так и файлами, которые можно приложить к описанию)
    """
    logger.debug("Perform callback command create_new_issue and get cancel button")
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer(
        text="Введите описание обращения",
        reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    )

    await state.set_state(CreateNewIssue.description)
    await state.update_data(description="")
    await state.update_data(files=[])


# @new_user_router.message(
#     StateFilter(CreateNewIssue.files),
#     StateFilter(CreateNewIssue.description),
#     F.text == str(UserButtonText.CREATE_ISSUE)
# )
@new_user_router.message(
    (StateFilter(CreateNewIssue.files) or StateFilter(CreateNewIssue.description)) and F.text == str(
        UserButtonText.CREATE_ISSUE)
)
async def confirm_crate_new_issue_command(
        message: types.Message,
        state: FSMContext
):
    data = await state.get_data()

    logger.debug(f"FSM State: {data}")
    logger.debug(f"get user information from itilium by telegram id {message.from_user.id}")
    user_data_from_itilium: dict | None = await ItiliumBaseApi.get_employee_data_by_identifier(message)

    if user_data_from_itilium is None:
        logger.debug("user not found in Itilium")
        await state.clear()
        await message.answer(
            text="Не удалось найти вас в системе ITILIUM",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # send date to itilium api for create issue
    try:
        response: Response = await ItiliumBaseApi.create_new_sc({
            "UUID": user_data_from_itilium["UUID"],
            "Description": data["description"],
            "shortDescription": Helpers.prepare_short_description_for_sc(data["description"]),
        }, data["files"])

        logger.debug(f"{response.status_code} | {response.text}")

        if response.status_code == httpx.codes.OK:
            await message.answer(
                text=f"Ваша завка успешно создана!\n\r{json.loads(response.text)}",
                reply_markup=types.ReplyKeyboardRemove()
            )
        else:
            logger.debug(f"{response.text}")
            await message.answer(
                text=f"Не удалось создать заявку. Ошибка сервера {response.text}\n\rПовотрите попытку позже",
                reply_markup=types.ReplyKeyboardRemove()
            )
    except Exception as e:
        logger.exception(e)
        await message.answer(f"Ошибка: {str(e)}")

    await state.clear()


# @new_user_router.message(CreateNewIssue.files or (CreateNewIssue.description and F.text))
@new_user_router.message(F.md_text and StateFilter(CreateNewIssue))
@new_user_router.message(F.html_text and StateFilter(CreateNewIssue))
@new_user_router.message(CreateNewIssue.files)
@new_user_router.message(StateFilter(CreateNewIssue.description))
# @new_user_router.message(StateFilter(CreateNewIssue.description), F.text)
async def set_description_for_issue(
        message: types.Message,
        state: FSMContext,
        bot: Bot
):
    """
    Метод позволяющий создать текст для нового обращения
    """
    logger.debug("enter description for new issue")

    # description = ""

    # if len(message.text) == 0:
    # await message.answer("Вы ввели пустое описание. Введите описание заного или отмените все действия")
    # return

    if message.text and len(message.text) > 0:
        # description = message.text
        await state.update_data(description=message.text)

    if message.html_text and len(message.html_text) > 0:
        await state.update_data(description=message.html_text)
    elif message.md_text and len(message.md_text) > 0:
        await state.update_data(description=message.md_text)

    data: dict = await state.get_data()
    description = data.get("description", "")

    if len(description) == 0:
        await message.answer("Вы ввели пустое описание. Введите описание заного или отмените все действия")
        return

    if (
            message.photo or
            message.video or
            message.voice or
            message.document
    ) is not None:
        file_path = await Helpers.get_file_info(message, bot)
        files: list = data.get("files", [])
        logger.debug(f"files: {files}")
        if files is None:
            await state.update_data(names=[])
        # files.append(file_path)

        if message.document is not None:
            filename = message.document.file_name
        else:
            filename = file_path

        files.append({
            "path": file_path,
            "filename": filename,
        })

    logger.debug(f"create_new_sc -> FSM data : {data}")
    # files =
    # await state.clear()

    await message.answer(
        text="Всё готово, можно отправлять.",
        reply_markup=get_keyboard(
            str(UserButtonText.CANCEL),
            str(UserButtonText.CREATE_ISSUE))
    )

    # await state.update_data(description=message.text)

    # await state.set_state(CreateNewIssue.files)
    # await state.update_data(files=[])
    # await message.answer(
    #     text=f"Описание добавлено. При необходмости, можете добавьте файлы к обращению. "
    #          f"Что бы подтвердить создание обращения, "
    #          f"нажмите кнопку '{str(UserButtonText.CREATE_ISSUE)}'",
    #     reply_markup=get_keyboard(
    #         str(UserButtonText.CANCEL),
    #         str(UserButtonText.CREATE_ISSUE))
    # )


@new_user_router.message(CreateNewIssue.files)
async def set_description_for_issue(
        message: types.Message,
        state: FSMContext,
        bot: Bot
):
    """
    Метод для добавления различных файлов к обращению
    """
    data = await state.get_data()

    if (
            message.photo or
            message.video or
            message.voice or
            message.document
    ) is not None:
        file_path = await Helpers.get_file_info(message, bot)
        files: list = data.get("files", [])

        logger.debug(f"files: {files}")

        if files is None:
            await state.update_data(names=[])

        # names.append({
        #     "filename": file_path.split("/")[-1],  # file_13.jpg
        #     "file": file_path  # photos/file_13.jpg
        # })

        files.append(file_path)

        await message.answer("Файл подготовлен к отправке")
        return


@new_user_router.callback_query(F.data.startswith("accept$"))
async def btn_accept(callback: types.CallbackQuery):
    """
    Обработчик кнопки "Согласовать"
    Переводит согласование в статус "Согласовано"
    Формирует сообщение о выполнении действия, либо об ошибке.
    Формат текста по нажатию на кнопку согласовать 'accept$000001844'
    """
    try:
        logger.debug(f"{callback.from_user.id} | {callback.data}")
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
        logger.debug(f"{callback.from_user.id} | {callback.data}")
        await ItiliumBaseApi.reject_callback_handler(callback)
        await callback.message.answer("Отклонено")
    except Exception as e:
        logger.error(e)
        await callback.answer("Во время согласования, произошла ошибка. Обратитесь к администратору")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("reply$"))
async def btn_reply_for_comment(
        callback: types.CallbackQuery,
        state: FSMContext
):
    """
    Обработчик кнопки "Добавить комментарий", когда пользователю приходит сообщение о согласовании
    (Кнопки в сообщении "Открыть заявку" и "Добавить комментарий")
    """
    logger.debug(f"callback reply$ {callback.from_user.id} | {callback.data}")
    await callback.answer()
    await callback.message.answer(
        "Введите коментарий или добавьте картинку. Для отмены, нажмите кнопку 'Отмена'",
        # reply_markup=get_keyboard(
        #     str(UserButtonText.CANCEL),
        #     str(UserButtonText.SEND_COMMENT)
        # )
        reply_markup=get_callback_btns(btns={
            "отмена": "cancel"
        })
    )
    await state.set_state(CreateComment.files)
    await state.update_data(sc_id=callback.data[6:])
    await state.update_data(files=[])


@new_user_router.callback_query(StateFilter(CreateComment.files), F.data.startswith("cancel"))
@new_user_router.callback_query(StateFilter(None), F.data.startswith("cancel"))
async def callback_cancel_btn(
        callback: types.CallbackQuery,
        state: FSMContext
):
    await state.clear()
    await callback.answer()
    await callback.message.delete()


@new_user_router.message(F.text == str(UserButtonText.SEND_COMMENT))
async def send_comment_for_sc_to_itilium(
        message: types.Message,
        state: FSMContext
):
    await message.answer(
        text="идёт отправка комментария... ",
        reply_markup=types.ReplyKeyboardRemove()
    )

    data: dict = await state.get_data()

    current_state = await state.get_state()
    logger.debug(f"state {current_state}")

    logger.debug(f"comment: {message.text}")
    # logger.debug(f"{message.from_user.id} | {data["sc_id"]}")
    logger.debug(f"files for comment: {data['files']}")

    try:
        response: Response = await ItiliumBaseApi.add_comment_to_sc(
            telegram_user_id=message.from_user.id,
            # comment=message.text,
            comment=data.get("comment", 'no comment'),
            sc_number=data["sc_id"],
            files=data["files"]
        )

        logger.debug("send comment to 1C itilium")
    except Exception as e:
        await message.answer("Проблемы на стороне Итилиума. Обратитесь к администратору.")
        logger.error(e)

    await state.clear()
    await message.answer(
        text='Комментарий добавлен',
        reply_markup=types.ReplyKeyboardRemove()
    )


@new_user_router.message(StateFilter(CreateComment.files))
@new_user_router.message(F.photo)
@new_user_router.message(F.video)
@new_user_router.message(F.voice)
@new_user_router.message(F.document)
async def test_filter(
        message: types.Message,
        state: FSMContext,
        bot: Bot
):
    data = await state.get_data()

    if (
            message.photo or
            message.video or
            message.voice or
            message.document
    ) is not None:
        file_path = await Helpers.get_file_info(message, bot)
        files: list = data.get("files", [])

        logger.debug(f"files: {files}")

        if files is None:
            await state.update_data(names=[])

        # names.append({
        #     "filename": file_path.split("/")[-1],  # file_13.jpg
        #     "file": file_path  # photos/file_13.jpg
        # })

        files.append(file_path)

        await message.answer("Файл подготовлен к отправке")
        # return

    await state.update_data(comment=message.text)
    await message.answer("Комментарий подготовлен к отправке")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("show_sc$"))
async def show_sc_info_callback(callback: types.CallbackQuery):
    """
    Метод, осуществляющий вывод информации о заявке
    """
    logger.debug(f"{callback.data}")
    sc_number = callback.data[8:]
    logger.info(f"{sc_number}")
    response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
    await callback.answer()

    if response is None:
        return await callback.message.answer(f"Заявка с номером {sc_number} не найдена")

    # Формируем текст сообщения
    message_text = Helpers.prepare_sc(response)

    if response["state"] != 'registered':
        btn = get_callback_btns(
            btns={
                "Скрыть информацию ↩️": "del_message",
                "Взять в работу ️ 🛠": "to_work{0}".format(sc_number),
            }
        )
    else:
        btn = get_callback_btns(
            btns={
                "Скрыть информацию ↩️": "del_message",
            }
        )

    await callback.message.answer(
        text=message_text,
        reply_markup=btn,
        parse_mode='HTML'
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("del_message"))
async def show_sc_info_callback(callback: types.CallbackQuery):
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("scs_client"))
async def show_sc_info_callback(callback: types.CallbackQuery):
    user = await ItiliumBaseApi.get_employee_data_by_identifier(callback)

    if user is None:
        await callback.answer()
        await callback.message.answer("1С Итилиум прислал пустой ответ. Обратитесь к администратору")
        return

    logger.debug(f"user: {user['servicecalls']}")

    await callback.answer()
    send_message_for_search = await callback.message.answer("Запрашиваю заявки, подождите...")

    # Start execute time
    start_time = time.time()

    my_scs: list = user['servicecalls']

    if not my_scs:
        await callback.answer()
        await send_message_for_search.delete()
        await callback.message.answer("У вас нет созданных заявок заявок")
        return

    # tasks = [ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc) for sc in my_scs]
    # results = await asyncio.gather(*tasks, return_exceptions=True)

    # results = await ItiliumBaseApi.get_task_for_async_find_sc_by_id(scs=my_scs, callback=callback)
    results = asyncio.run(ItiliumBaseApi.get_task_for_async_find_sc_by_id(scs=my_scs, callback=callback))

    end_time = time.time()
    execution_time = end_time - start_time
    logger.debug(f"execution time: {execution_time}")
    # Stop execute time

    scs: list = [sc for sc in results if sc is not None]

    data_with_pagination = await Helpers.get_paginated_kb_scs(scs)

    await send_message_for_search.delete()
    await callback.message.answer(
        text="Ваши обращения",
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("sc_page_"))
async def show_sc_info_pagination_callback(callback: types.CallbackQuery):
    # Start execute time
    start_time = time.time()

    page = callback.data.split("sc_page_")[1]
    user = await ItiliumBaseApi.get_employee_data_by_identifier(callback)
    my_scs: list = user['servicecalls']

    tasks = [ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc) for sc in my_scs]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    end_time = time.time()
    execution_time = end_time - start_time
    logger.debug(f"execution time: {execution_time}")
    # Stop execute time

    scs: list = [sc for sc in results if sc is not None]

    # data_with_pagination = await Helpers.get_paginated_kb_scs(scs)

    data_with_pagination = await Helpers.get_paginated_kb_scs(scs, int(page))

    await callback.message.edit_reply_markup(
        reply_markup=data_with_pagination
    )

    # await callback.message.answer(
    #     text="Ваши обращения",
    #     reply_markup=data_with_pagination
    # )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("delete_sc_pagination"))
async def delete_scs_list_pagination(callback: types.CallbackQuery):
    await callback.message.delete()


@new_user_router.callback_query()
async def btn_all_callback(callback: types.CallbackQuery):
    """
    Обработчик ловит любые Callback
    """
    a = callback.data
    # show_sc$0000023773 при нажатии на кнопку "Открыть заявку"
    # reply$0000023773 при нажатии на кнопку "Добавить комментарий"
    logger.debug(f"unknown callback | {callback.from_user.id} | {callback.data}")
    await callback.answer()


@new_user_router.message(F.text)
async def magic_filter(
        message: types.Message,
        state: FSMContext
):
    """
    Магический фильтр, который ловит все необработанные сообщения.
    """
    # try:
    #     async with httpx.AsyncClient() as client:
    #         json_data = json.dumps([
    #             {
    #                 'filename': 'file.jpg',
    #                 'file': 'photos/file.jpg',
    #             },
    #             {
    #                 'filename': 'document.exe',
    #                 'file': 'documents/document.exe',
    #             },
    #             {
    #                 'filename': 'video.mp4',
    #                 'file': 'videos/video.mp4',
    #             },
    #             {
    #                 'filename': 'voice.oga',
    #                 'file': 'voice/voice.oga',
    #             },
    #         ], )
    #
    # response = await client.request( # headers={ #     'Content-Type': 'multipart/form-data', # }, method="POST",
    # url="http://telegrambot_api_nginx/api/test", data={ "description": "lorem ipsum dollar sit amet", # "files":
    # json_data "files": '[{"filename": "file_14.jpg", "file": "photos/file_14.jpg"}, {"filename": "file_17.jpg",
    # ' '"file": "photos/file_17.jpg"}]' }, timeout=30.0 )
    #
    #         logger.debug(f"status {response.status_code} | {response.text}")
    # except Exception as e:
    #     logger.exception(e)
    await message.answer(text="Я не понимаю Вашей команды (((")
