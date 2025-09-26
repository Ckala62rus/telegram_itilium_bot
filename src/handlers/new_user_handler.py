import json
import logging
import re

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram_dialog import DialogManager
from httpx import Response

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserButtonText
from dialogs.bot_menu.states import ChangeScStatus
from dto.paginate_scs_dto import PaginateScsDTO
from dto.paginate_scs_responsible_dto import PaginateResponsibleScsDTO
from dto.paginate_teams_dto import PaginateTeamsDTO
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue, CreateComment, SearchSC, LoadPagination, ConfirmSc, LoadPaginationResponsible
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
from kbds.user_kbds import USER_MENU_KEYBOARD
from services.user_private_service import base_start_handler, paginate_scs_logic, paginate_responsible_scs_logic, paginate_teams_logic
from utils.helpers import Helpers
from utils.message_templates import MessageTemplates, MessageFormatter, ButtonTemplates

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
            MessageTemplates.ACTIONS_CANCELED_SIMPLE,
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
    выводится в зависимости от типа пользователя (сотрудник IT/нет)
    """

    await message.delete()
    await state.clear()
    logger.debug("command or message -> menu")

    logger.debug("Отправляем inline кнопки меню")
    await message.answer(MessageTemplates.CHOOSE_MENU_ITEM, reply_markup=USER_MENU_KEYBOARD)


@new_user_router.callback_query(StateFilter(None), F.data.startswith("crate_new_issue"))
async def crate_new_issue_command(callback: types.CallbackQuery, state: FSMContext):
    """
    Метод инициирует создание нового обращения с FSM состоянием.
    (Обращение создается как с текстом, так и файлами, которые можно приложить к описанию)
    """
    logger.debug("Perform callback command create_new_issue and get cancel button")
    await callback.answer()

    await callback.message.answer(
        text=MessageTemplates.ENTER_ISSUE_DESCRIPTION,
        reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    )

    await state.set_state(CreateNewIssue.description)
    await state.update_data(description="")
    await state.update_data(files=[])


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


@new_user_router.message(F.md_text and StateFilter(CreateNewIssue))
@new_user_router.message(F.html_text and StateFilter(CreateNewIssue))
@new_user_router.message(CreateNewIssue.files)
@new_user_router.message(StateFilter(CreateNewIssue.description))
async def set_description_for_issue(
        message: types.Message,
        state: FSMContext,
        bot: Bot
):
    """
    Метод позволяющий создать текст для нового обращения
    """
    logger.debug("enter description for new issue")

    if message.text and len(message.text) > 0:
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

        if message.document is not None:
            filename = message.document.file_name
        else:
            filename = file_path

        files.append({
            "path": file_path,
            "filename": filename,
        })

    logger.debug(f"create_new_sc -> FSM data : {data}")

    await message.answer(
        text="Всё готово, можно отправлять.",
        reply_markup=get_keyboard(
            str(UserButtonText.CANCEL),
            str(UserButtonText.CREATE_ISSUE))
    )


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
        await callback.message.answer(MessageTemplates.AGREED)
    except Exception as e:
        logger.error(e)
        await callback.answer(MessageTemplates.AGREEMENT_ERROR)


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
        reply_markup=get_callback_btns(btns={
            "отмена": "cancel"
        })
    )
    await state.set_state(CreateComment.files)
    await state.update_data(sc_id=callback.data[6:])
    await state.update_data(files=[])


@new_user_router.callback_query(StateFilter(CreateComment.files), F.data.startswith("cancel"))
@new_user_router.callback_query(StateFilter(None), F.data.startswith("cancel"))
@new_user_router.callback_query(StateFilter("*"), F.data.startswith("cancel"))
async def callback_cancel_btn(
        callback: types.CallbackQuery,
        state: FSMContext
):
    """
    Обработчик кнопки "отмена".
    Удаляется сообщение с кнопкой "отмена", так же очищается машина состояние FSM
    """
    await state.clear()
    await callback.answer()
    await callback.message.delete()


@new_user_router.message(F.text == str(UserButtonText.SEND_COMMENT))
async def send_comment_for_sc_to_itilium(
        message: types.Message,
        state: FSMContext
):
    """
    Обработчик кнопки "Отправить комментарий".
    Так же происходит отправка файлов, приткрепленных к коментарию.
    """
    await message.answer(
        text="идёт отправка комментария... ",
        reply_markup=types.ReplyKeyboardRemove()
    )

    data: dict = await state.get_data()

    current_state = await state.get_state()
    logger.debug(f"state {current_state}")

    logger.debug(f"comment: {message.text}")
    logger.debug(f"files for comment: {data['files']}")

    try:
        response: Response = await ItiliumBaseApi.add_comment_to_sc(
            telegram_user_id=message.from_user.id,
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
    """
    Обработчик отвечающий за получение названий файлов и подготовку ссылок, через которые Итилиум их скачает.
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

        files.append(file_path)

        await message.answer("Файл подготовлен к отправке")

    await state.update_data(comment=message.text)

    await message.answer(
        text="Комментарий подготовлен к отправке",
        reply_markup=get_keyboard(
            str(UserButtonText.CANCEL),
            str(UserButtonText.SEND_COMMENT)
        )
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("show_sc$"))
async def show_sc_info_callback(callback: types.CallbackQuery):
    """
    Метод, осуществляющий вывод информации о заявке
    """
    logger.debug(f"{callback.data}")
    sc_number = callback.data[8:]
    logger.info(f"{sc_number}")

    try:
        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
    except Exception as e:
        logger.debug(f"error for {callback.from_user.id} {sc_number} {e}")
        logger.exception(e)
        await callback.answer()
        await callback.message.answer(MessageTemplates.ITILIUM_ERROR)
        return None

    await callback.answer()

    if response is None:
        return await callback.message.answer(MessageFormatter.issue_not_found(sc_number))

    # logger.debug(f"find_sc_by_id | {response}")

    # Формируем текст сообщения
    message_text = Helpers.prepare_sc(response)

    btns: dict = {}

    if response["state"] != 'registered':
        btns = ButtonTemplates.hide_and_change_status(sc_number)
        # Добавляем кнопку смены ответственного если поле change_responsible равно true
        if response.get("change_responsible") == True:
            btns["Сменить ответственного 👤"] = f"change_responsible${sc_number}"
    else:
        btns = ButtonTemplates.hide_info()

    btn_keyboard = get_callback_btns(btns=btns, size=(1,))

    await callback.message.answer(
        text=message_text,
        reply_markup=btn_keyboard,
        parse_mode='HTML'
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("show_state$"))
async def hide_sc_info_callback(callback: types.CallbackQuery, bot: Bot):
    """
    Обработчик кнопки "Поменять статус"
    """
    sc_number = callback.data[11:]
    await callback.answer()
    logger.debug(f"hide sc by number {sc_number}")

    try:
        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
    except Exception as e:
        logger.debug(f"error for {callback.from_user.id} {sc_number} {e}")
        logger.exception(e)
        await callback.answer()
        await callback.message.answer(MessageTemplates.ITILIUM_ERROR)
        return None

    btns: dict = {}

    if response["new_state"]:
        btns["Назад ↩️"] = f"back_change_status${sc_number}"
        for state in response["new_state"]:
            btns[f"{state} ✏"] = f"ch_st_{sc_number}${state}"


    btn_keyboard = get_callback_btns(btns=btns, size=(1,2))

    await callback.message.edit_reply_markup(
        reply_markup=btn_keyboard
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("back_change_status$"))
async def hide_sc_info_callback(callback: types.CallbackQuery):
    """
    Обработчик для скрытия статусов задачи
    """
    btns: dict = {}
    sc_number = callback.data[19:]
    await callback.answer()

    # Восстанавливаем набор кнопок, включая "Сменить ответственного", если доступно
    btns = {
        "Скрыть информацию ↩️": "del_message",
        "Поменять статус 🔁": f"show_state${sc_number}",
    }

    try:
        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
        if response and response.get("change_responsible") is True:
            btns["Сменить ответственного 👤"] = f"change_responsible${sc_number}"
    except Exception:
        pass

    btn_keyboard = get_callback_btns(btns=btns, size=(1,))

    await callback.message.edit_reply_markup(
        reply_markup=btn_keyboard
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("ch_st_"))
async def hide_sc_info_callback(
    callback: types.CallbackQuery,
    bot: Bot,
    dialog_manager: DialogManager,
):
    """
    Обработчик для смены статуса задачи (отложено, в работе, на согласование и т.д.)
    """
    await callback.answer()

    logger.debug(f"change status for sc => {callback.data}")
    data: str = callback.data[6:]
    data_after_split = data.split("$")

    sc_number = data_after_split[0]
    new_state = data_after_split[1]

    logger.debug(f"sc number => {sc_number}")
    logger.debug(f"sc status => {new_state}")

    """
    Если статус 'Отложено', то нам необходимо запросить комментарий и дату,
    на которое число, необходимо отложить задачу.
    """
    if new_state == "05_Отложено" or new_state == "06_В ожидании ответа":
        await dialog_manager.start(
            state=ChangeScStatus.enter_comment,
            data={
                "sc_number": sc_number,
                "new_state": new_state
            })
        return

    waiting_message = await callback.message.answer(
        text="Меняю статус, подождите..."
    )

    result: Response = await ItiliumBaseApi.change_sc_state(
        telegram_user_id=callback.from_user.id,
        sc_number=sc_number,
        state=new_state
    )

    if result.status_code == httpx.codes.OK:
        # Получаем обновленные данные заявки
        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
        
        # Формируем кнопки
        btns = {
            "Скрыть информацию ↩️": "del_message",
            "Поменять статус 🔁": f"show_state${sc_number}",
        }
        
        # Добавляем кнопку смены ответственного если поле change_responsible равно true
        if response and response.get("change_responsible") == True:
            btns["Сменить ответственного 👤"] = f"change_responsible${sc_number}"
        
        btn_keyboard = get_callback_btns(btns=btns, size=(1,))
        
        # Формируем текст сообщения
        message_text = Helpers.prepare_sc(response)

        await waiting_message.delete()

        await bot.edit_message_text(
            text=message_text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            parse_mode='HTML'
        )

        await callback.message.edit_reply_markup(
            reply_markup=btn_keyboard
        )

    logger.debug(f"change state sc result => {result}")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("scs_search"))
async def search_sc_by_number_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик для логики поиска заявки по номеру
    """
    await callback.answer()
    await state.set_state(SearchSC.sc_number)
    preview_message = await callback.message.answer(
        text=MessageTemplates.ENTER_ISSUE_NUMBER,
        reply_markup=get_callback_btns(btns=ButtonTemplates.cancel())
    )
    await state.update_data(preview_message=preview_message)


@new_user_router.message(SearchSC.sc_number)
async def handler_perform_search_for_sc_by_number(
        message: types.Message,
        state: FSMContext,
):
    """
    Обработчик поиска заявки по номеру, после ввода номера пользователем.
    """
    looking_for = await message.answer(MessageTemplates.ISSUE_LOOKING)
    state_data = await state.get_data()
    sc_number = message.text
    logger.debug(f"find sc by number {sc_number}")
    try:
        result: dict | None = await ItiliumBaseApi.find_sc_by_id(message.from_user.id, sc_number)
        logger.debug(f"find sc by number. response {sc_number}")
    except Exception as e:
        logger.debug(f"error for {message.from_user.id} {sc_number} {e}")
        await state.clear()
        await message.answer(MessageFormatter.issue_search_error(str(e)))
        await looking_for.delete()
        return

    if isinstance(result, str):
        await message.answer(MessageFormatter.issue_search_result(sc_number, result))
    else:
        await message.answer(
            text=Helpers.prepare_sc(result),
            parse_mode='HTML',
            reply_markup=get_callback_btns(btns=ButtonTemplates.hide_info())
        )

    await state.clear()
    await message.delete()
    await looking_for.delete()
    await state_data["preview_message"].delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("del_message"))
async def hide_sc_info_callback(callback: types.CallbackQuery):
    """
    Обработчик кнопки "Скрыть информацию"
    """
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("change_responsible$"))
async def change_responsible_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик кнопки "Сменить ответственного"
    """
    sc_number = callback.data[19:]  # Убираем "change_responsible$"
    user_id = callback.from_user.id
    
    paginate_dto: PaginateTeamsDTO = PaginateTeamsDTO(user_id=user_id, sc_number=sc_number)
    
    await callback.answer()
    
    # Сохраняем sc_number в состоянии
    await state.update_data(sc_number=sc_number)
    
    send_message_for_search = None
    
    if not await paginate_dto.exists():
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)
        
        logger.debug(f"key with name {user_id} is not exist in Redis!")
        result: dict = await paginate_teams_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)
        
        # извлекаем из редиса
        teams = await paginate_dto.get_cache_teams()
    else:
        teams = await paginate_dto.get_cache_teams()
    
    data_with_pagination = await Helpers.get_paginated_kb_teams(teams)
    
    if send_message_for_search:
        await send_message_for_search.delete()
    
    # Очищаем состояние загрузки, но сохраняем sc_number
    await state.clear()
    await state.update_data(sc_number=sc_number)
    
    await callback.message.answer(
        text="Выберите подразделение:",
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("teams_page_"))
@new_user_router.callback_query(StateFilter(LoadPagination.load), F.data.startswith("teams_page_"))
async def show_teams_pagination_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик кнопок постраничной навигации в отображении списка подразделений
    """
    user_id = callback.from_user.id
    teams = None
    send_message_for_search = None

    # Получаем sc_number из состояния
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return

    paginate_dto: PaginateTeamsDTO = PaginateTeamsDTO(user_id=user_id, sc_number=sc_number)

    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    send_message_for_search = None
    
    if not await paginate_dto.exists():
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {callback.from_user.id} is not exist in Redis!")
        result: dict = await paginate_teams_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        teams = await paginate_dto.get_cache_teams()
    else:
        teams = await paginate_dto.get_cache_teams()

    data_with_pagination = await Helpers.get_paginated_kb_teams(teams, int(callback.data.split("teams_page_")[1]))

    if send_message_for_search:
        await send_message_for_search.delete()

    # Очищаем состояние загрузки, но сохраняем sc_number
    await state.clear()
    await state.update_data(sc_number=sc_number)

    await callback.message.edit_reply_markup(
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("select_team$"))
async def select_team_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора подразделения
    """
    team_id = callback.data[12:]  # Убираем "select_team$"
    user_id = callback.from_user.id
    
    # Получаем sc_number из состояния
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return
    
    # Сохраняем выбранное подразделение
    await state.update_data(selected_team_id=team_id)
    
    # Получаем сотрудников выбранного подразделения
    try:
        response = await ItiliumBaseApi.get_responsibles(user_id, sc_number)
        if response.status_code == 200:
            responsibles_data = response.json()
            
            # Находим выбранное подразделение
            selected_team = None
            for team in responsibles_data:
                if team['responsibleTeamId'] == team_id:
                    selected_team = team
                    break
            
            if selected_team:
                employees = selected_team['responsibles']
                data_with_pagination = await Helpers.get_paginated_kb_employees(employees)
                
                await callback.message.edit_text(
                    text="Выберите ответственного:",
                    reply_markup=data_with_pagination
                )
            else:
                await callback.answer("Подразделение не найдено")
        else:
            await callback.answer("Ошибка получения данных")
    except Exception as e:
        logger.error(f"Error getting responsibles: {e}")
        await callback.answer("Ошибка получения данных")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("employees_page_"))
async def show_employees_pagination_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик кнопок постраничной навигации в отображении списка сотрудников
    """
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    team_id = state_data.get('selected_team_id')
    
    if not sc_number or not team_id:
        await callback.answer("Ошибка: данные не найдены")
        return

    await callback.answer()

    try:
        response = await ItiliumBaseApi.get_responsibles(user_id, sc_number)
        if response.status_code == 200:
            responsibles_data = response.json()
            
            # Находим выбранное подразделение
            selected_team = None
            for team in responsibles_data:
                if team['responsibleTeamId'] == team_id:
                    selected_team = team
                    break
            
            if selected_team:
                employees = selected_team['responsibles']
                page = int(callback.data.split("employees_page_")[1])
                data_with_pagination = await Helpers.get_paginated_kb_employees(employees, page)
                
                await callback.message.edit_reply_markup(
                    reply_markup=data_with_pagination
                )
            else:
                await callback.answer("Подразделение не найдено")
        else:
            await callback.answer("Ошибка получения данных")
    except Exception as e:
        logger.error(f"Error getting employees: {e}")
        await callback.answer("Ошибка получения данных")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("select_employee$"))
async def select_employee_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора сотрудника
    """
    employee_id = callback.data[16:]  # Убираем "select_employee$"
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return
    
    # Сохраняем выбранного сотрудника
    await state.update_data(selected_employee_id=employee_id)
    
    await callback.answer()
    
    # Показываем подтверждение
    btns = {
        "Назад к подразделениям ⬅️": "back_to_teams",
        "Назад к сотрудникам ⬅️": "back_to_employees",
        "Отмена ❌": "cancel_change_responsible",
        "Подтвердить ✅": f"confirm_change_responsible${employee_id}"
    }
    
    btn_keyboard = get_callback_btns(btns=btns, size=(2,))
    
    await callback.message.edit_text(
        text=f"Подтвердите смену ответственного для заявки №{sc_number}",
        reply_markup=btn_keyboard
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("confirm_change_responsible$"))
async def confirm_change_responsible_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик подтверждения смены ответственного
    """
    employee_id = callback.data[28:]  # Убираем "confirm_change_responsible$"
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return
    
    await callback.answer()
    
    send_data_to_api = await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text="Меняю ответственного. Подождите!"
    )
    
    try:
        result: Response = await ItiliumBaseApi.change_responsible(
            telegram_user_id=user_id,
            sc_number=sc_number,
            responsible_employee_id=employee_id
        )
        
        if result.status_code == 200:
            await send_data_to_api.delete()
            
            # Получаем информацию о назначенном сотруднике
            try:
                response = await ItiliumBaseApi.get_responsibles(user_id, sc_number)
                if response.status_code == 200:
                    responsibles_data = response.json()
                    
                    # Находим назначенного сотрудника
                    assigned_employee = None
                    for team in responsibles_data:
                        for employee in team['responsibles']:
                            if employee['responsibleEmployeeId'] == employee_id:
                                assigned_employee = employee
                                break
                        if assigned_employee:
                            break
                    
                    if assigned_employee:
                        await callback.bot.send_message(
                            chat_id=callback.from_user.id,
                            text=f"✅ Для заявки №{sc_number} назначен новый ответственный: {assigned_employee['responsibleEmployeeTitle']}"
                        )
                    else:
                        await callback.bot.send_message(
                            chat_id=callback.from_user.id,
                            text=f"✅ Для заявки №{sc_number} назначен новый ответственный"
                        )
                else:
                    await callback.bot.send_message(
                        chat_id=callback.from_user.id,
                        text=f"✅ Для заявки №{sc_number} назначен новый ответственный"
                    )
            except Exception as e:
                logger.error(f"Error getting employee info: {e}")
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=f"✅ Для заявки №{sc_number} назначен новый ответственный"
                )
        else:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"""
                Что-то пошло не так... 💥
                Ошибка: {result.text}
                """
            )
    except Exception as e:
        logger.error(f"Error changing responsible: {e}")
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Ошибка при смене ответственного"
        )
    
    await state.clear()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("cancel_change_responsible"))
async def cancel_change_responsible_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик отмены смены ответственного - возвращает к детальному просмотру заявки
    """
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    await callback.answer()
    await state.clear()
    
    if not sc_number:
        await callback.message.edit_text("Отмена")
        return
    
    # Получаем данные заявки
    try:
        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
        
        if response is None:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text="Заявка не найдена"
            )
            return
        
        # Формируем текст сообщения
        message_text = Helpers.prepare_sc(response)
        
        # Формируем кнопки
        btns = {
            "Скрыть информацию ↩️": "del_message",
            "Поменять статус 🔁": f"show_state${sc_number}",
        }
        
        # Добавляем кнопку смены ответственного если поле change_responsible равно true
        if response.get("change_responsible") == True:
            btns["Сменить ответственного 👤"] = f"change_responsible${sc_number}"
        
        btn_keyboard = get_callback_btns(btns=btns, size=(1,))
        
        await callback.message.edit_text(
            text=message_text,
            reply_markup=btn_keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error getting SC details: {e}")
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Ошибка при получении данных заявки"
        )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("delete_teams_pagination"))
async def delete_teams_pagination_callback(callback: types.CallbackQuery):
    """
    Обработчик кнопки удаления пагинации подразделений
    """
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("delete_employees_pagination"))
async def delete_employees_pagination_callback(callback: types.CallbackQuery):
    """
    Обработчик кнопки удаления пагинации сотрудников
    """
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("assign_to_team"))
async def assign_to_team_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик кнопки "Назначить на подразделение"
    """
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    team_id = state_data.get('selected_team_id')
    
    if not sc_number or not team_id:
        await callback.answer("Ошибка: данные не найдены")
        return
    
    await callback.answer()
    
    # Показываем подтверждение для назначения на подразделение
    btns = {
        "Назад ⬅️": "back_to_employees",
        "Отмена ❌": "cancel_change_responsible",
        "Подтвердить ✅": f"confirm_assign_to_team${team_id}"
    }
    
    btn_keyboard = get_callback_btns(btns=btns, size=(2,))
    
    await callback.message.edit_text(
        text=f"Подтвердите назначение на подразделение для заявки №{sc_number}",
        reply_markup=btn_keyboard
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("scs_client"))
@new_user_router.callback_query(StateFilter(LoadPagination.load), F.data.startswith("scs_client"))
async def show_all_client_scs_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик кнопки "Мои заявки".
    Выводится весь список созданных мной заявок, с постраничной навигацией
    """
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateScsDTO = PaginateScsDTO(user_id=user_id)

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not await paginate_dto.exists():
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {user_id} is not exist in Redis!")
        result: dict = await paginate_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = await paginate_dto.get_cache_scs()
    else:
        scs = await paginate_dto.get_cache_scs()

    data_with_pagination = await Helpers.get_paginated_kb_scs(scs)

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.answer(
        text=MessageTemplates.YOUR_REQUESTS,
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("sc_page_"))
@new_user_router.callback_query(StateFilter(LoadPagination.load), F.data.startswith("sc_page_"))
async def show_sc_info_pagination_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик кнопок постраничной навигации в отображении списка, созданных мною заявок
    """
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateScsDTO = PaginateScsDTO(user_id=user_id)

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not await paginate_dto.exists():
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {callback.from_user.id} is not exist in Redis!")
        result: dict = await paginate_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = await paginate_dto.get_cache_scs()
        await state.clear()
    else:
        scs = await paginate_dto.get_cache_scs()

    data_with_pagination = await Helpers.get_paginated_kb_scs(scs, int(callback.data.split("sc_page_")[1]))

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.edit_reply_markup(
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("responsibility_scs_client"))
@new_user_router.callback_query(StateFilter(LoadPaginationResponsible.load), F.data.startswith("responsibility_scs_client"))
async def show_responsibility_scs_client(
    callback: types.CallbackQuery,
    state: FSMContext,
):
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    paginate_dto: PaginateResponsibleScsDTO = PaginateResponsibleScsDTO(user_id=user_id)

    if is_loading:
        return

    if not await paginate_dto.exists():
        result: dict = await paginate_responsible_scs_logic(callback, paginate_dto)

        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = await paginate_dto.get_cache_responsible_scs()
    else:
        scs = await paginate_dto.get_cache_responsible_scs()

    data_with_pagination = await Helpers.get_paginated_kb_responsible_scs(scs)

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.answer(
        text=MessageTemplates.RESPONSIBLE_REQUESTS,
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("responsible_sc_page_"))
@new_user_router.callback_query(StateFilter(LoadPaginationResponsible.load), F.data.startswith("responsible_sc_page_"))
async def show_sc_info_pagination_callback(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    Обработчик кнопок постраничной навигации в отображении списка, созданных мною заявок
    """
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateResponsibleScsDTO = PaginateResponsibleScsDTO(user_id=user_id)

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not await paginate_dto.exists():
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {callback.from_user.id} is not exist in Redis!")
        result: dict = await paginate_responsible_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = await paginate_dto.get_cache_responsible_scs()
        await state.clear()
    else:
        scs = await paginate_dto.get_cache_responsible_scs()

    data_with_pagination = await Helpers.get_paginated_kb_responsible_scs(scs, int(callback.data.split("responsible_sc_page_")[1]))

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.edit_reply_markup(
        reply_markup=data_with_pagination
    )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("delete_sc_pagination"))
async def delete_scs_list_pagination(callback: types.CallbackQuery):
    """
    Обработчик кнопки удаления списка, созданных мною заявок, с постраничной навигации
    """
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("delete_responsible_sc_pagination"))
async def delete_scs_list_pagination(callback: types.CallbackQuery):
    """
    Обработчик кнопки удаления списка (пагинации) заявок в моей ответственности
    """
    await callback.message.delete()


@new_user_router.callback_query(StateFilter(None), F.data.startswith("sc$"))
async def confirm_sc_handler(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    """
    При закрытии заявки, в чат прилетает общение о том, что ножно оставить сообщение.
    Обработчик обрабатывает оценку от 0 до 5
    """
    await callback.answer()

    # ^sc\$([0-9]{10})&mark\$([0-9]{1}).*$
    # sc$0000023770&mark$0
    try:
        m = re.search('^sc\\$([0-9]{10})&mark\\$([0-9]{1}).*$', callback.data)
        sc_number = m.group(1)
        mark = m.group(2)
        logger.debug(f"callback {callback.data} | sc_number {sc_number} | mark {mark}")
        await state.set_state(ConfirmSc.grade)
        await state.update_data(grade=mark, sc_number=sc_number, message_with_choice_grade=callback.message)
        await callback.message.answer(
            text=MessageFormatter.your_grade(mark),
            reply_markup=get_callback_btns(btns=ButtonTemplates.grade_actions())
        )
    except Exception as e:
        logger.error(f"error: {e}")


@new_user_router.callback_query(StateFilter(ConfirmSc.grade), F.data.startswith("send_confirm_sc"))
@new_user_router.callback_query(StateFilter(ConfirmSc.comment), F.data.startswith("send_confirm_sc"))
async def set_grade_for_confirm_sc_handler(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    data: dict = await state.get_data()
    grade = int(data["grade"])
    comment = data.get("comment", None)
    message_ids: list = data.get("messages_ids", [])
    message_with_choice_grade: types.Message = data.get("message_with_choice_grade")

    await callback.answer()

    logger.debug(data)

    if grade in [0, 1, 2] and comment is None:
        await callback.message.delete()
        message = await callback.message.answer(
            text=MessageFormatter.grade_comment_required(grade),
            reply_markup=get_callback_btns(btns=ButtonTemplates.grade_actions())
        )

        message_ids.append(message.message_id)
        await state.update_data(messages_ids=message_ids)

        await state.set_state(ConfirmSc.comment)
        return

    if message_ids:
        await callback.message.bot.delete_messages(
            chat_id=callback.message.chat.id,
            message_ids=message_ids
        )

    response: Response = await ItiliumBaseApi.confirm_sc(
        telegram_user_id=callback.from_user.id,
        sc_number=data["sc_number"],
        mark=data["grade"],
        comment=data["comment"] if comment else None
    )

    if response and response.status_code == httpx.codes.OK:
        await callback.message.edit_reply_markup(str(message_with_choice_grade), reply_markup=None)
        await message_with_choice_grade.edit_reply_markup(str(message_with_choice_grade), reply_markup=None)

        await callback.message.delete()
        await callback.message.answer(text=f"Ваша оценка ({data['grade']}) отправлена!")
    await state.clear()


@new_user_router.callback_query(StateFilter(ConfirmSc.grade), F.data.startswith("add_confirm_sc_comment"))
@new_user_router.callback_query(StateFilter(ConfirmSc.comment), F.data.startswith("add_confirm_sc_comment"))
async def set_comment_for_confirm_sc_handler(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    logger.debug("Оставляем комментарий")
    await callback.answer()

    new_message = await callback.message.answer(
        text=f"Введите комментарий или нажмите кнопку отмена",
        reply_markup=get_callback_btns(
            btns={
                "отмена ❌": "cancel",
            }
        )
    )

    data: dict = await state.get_data()
    message_ids: list = data.get("messages_ids", [])
    message_ids.append(new_message.message_id)

    await state.update_data(messages_ids=message_ids)
    await state.set_state(ConfirmSc.comment)


@new_user_router.message(StateFilter(ConfirmSc.comment))
async def set_comment_for_confirm_sc_handler(
        message: types.Message,
        state: FSMContext,
):
    data: dict = await state.get_data()
    message_ids: list | None = data.get("messages_ids", None)
    message_ids.append(message.message_id)
    await state.update_data(messages_ids=message_ids)

    comment = message.text
    message = await message.answer(
        text=f"Ваш комментарий: {comment}",
        reply_markup=get_callback_btns(
            btns={
                "отмена ❌": "cancel",
                "отправить оценку 📩": "send_confirm_sc",
            }
        )
    )

    await state.update_data(comment=comment)

    data: dict = await state.get_data()
    logger.debug(data)


@new_user_router.callback_query(StateFilter(None), F.data.startswith("back_to_teams"))
async def back_to_teams_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик кнопки "Назад к подразделениям" - возвращает к списку подразделений
    """
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return
    
    await callback.answer()
    
    # Получаем подразделения из кэша
    try:
        paginate_dto: PaginateTeamsDTO = PaginateTeamsDTO(user_id=callback.from_user.id, sc_number=sc_number)
        
        if await paginate_dto.exists():
            teams = await paginate_dto.get_cache_teams()
            data_with_pagination = await Helpers.get_paginated_kb_teams(teams)
            
            await callback.message.edit_text(
                text="Выберите подразделение:",
                reply_markup=data_with_pagination
            )
        else:
            await callback.answer("Данные не найдены. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error getting teams: {e}")
        await callback.answer("Ошибка получения данных")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("back_to_employees"))
async def back_to_employees_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик кнопки "Назад к сотрудникам" - возвращает к списку сотрудников
    """
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    team_id = state_data.get('selected_team_id')
    
    if not sc_number or not team_id:
        await callback.answer("Ошибка: данные не найдены")
        return
    
    await callback.answer()
    
    # Получаем сотрудников выбранного подразделения
    try:
        response = await ItiliumBaseApi.get_responsibles(callback.from_user.id, sc_number)
        if response.status_code == 200:
            responsibles_data = response.json()
            
            # Находим выбранное подразделение
            selected_team = None
            for team in responsibles_data:
                if team['responsibleTeamId'] == team_id:
                    selected_team = team
                    break
            
            if selected_team:
                employees = selected_team['responsibles']
                data_with_pagination = await Helpers.get_paginated_kb_employees(employees)
                
                await callback.message.edit_text(
                    text="Выберите ответственного:",
                    reply_markup=data_with_pagination
                )
            else:
                await callback.answer("Подразделение не найдено")
        else:
            await callback.answer("Ошибка получения данных")
    except Exception as e:
        logger.error(f"Error getting employees: {e}")
        await callback.answer("Ошибка получения данных")


@new_user_router.callback_query(StateFilter(None), F.data.startswith("confirm_assign_to_team$"))
async def confirm_assign_to_team_callback(
    callback: types.CallbackQuery,
    state: FSMContext
):
    """
    Обработчик подтверждения назначения на подразделение
    """
    team_id = callback.data[25:]  # Убираем "confirm_assign_to_team$"
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    sc_number = state_data.get('sc_number')
    
    if not sc_number:
        await callback.answer("Ошибка: номер заявки не найден")
        return
    
    await callback.answer()
    
    send_data_to_api = await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text="Назначаю на подразделение. Подождите!"
    )
    
    try:
        # Для назначения на подразделение используем team_id как responsibleEmployeeId
        result: Response = await ItiliumBaseApi.change_responsible(
            telegram_user_id=user_id,
            sc_number=sc_number,
            responsible_employee_id=team_id
        )
        
        await send_data_to_api.delete()
        
        if result.status_code == 200:
            # Получаем информацию о назначенном подразделении
            try:
                response = await ItiliumBaseApi.get_responsibles(user_id, sc_number)
                if response.status_code == 200:
                    responsibles_data = response.json()
                    
                    # Находим назначенное подразделение
                    assigned_team = None
                    for team in responsibles_data:
                        if team['responsibleTeamId'] == team_id:
                            assigned_team = team
                            break
                    
                    if assigned_team:
                        await callback.bot.send_message(
                            chat_id=callback.from_user.id,
                            text=f"✅ Для заявки №{sc_number} назначено подразделение: {assigned_team['responsibleTeamTitle']}"
                        )
                    else:
                        await callback.bot.send_message(
                            chat_id=callback.from_user.id,
                            text=f"✅ Для заявки №{sc_number} назначено подразделение"
                        )
                else:
                    await callback.bot.send_message(
                        chat_id=callback.from_user.id,
                        text=f"✅ Для заявки №{sc_number} назначено подразделение"
                    )
            except Exception as e:
                logger.error(f"Error getting team info: {e}")
                await callback.bot.send_message(
                    chat_id=callback.from_user.id,
                    text=f"✅ Для заявки №{sc_number} назначено подразделение"
                )
        else:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"""
                Что-то пошло не так... 💥
                Ошибка: {result.text}
                """
            )
    except Exception as e:
        logger.error(f"Error assigning to team: {e}")
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Ошибка при назначении на подразделение"
        )
    
    await state.clear()


@new_user_router.callback_query()
async def btn_all_callback(callback: types.CallbackQuery):
    """
    Обработчик ловит любые Callback
    """
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
    await message.answer(text="Я не понимаю Вашей команды (((")
