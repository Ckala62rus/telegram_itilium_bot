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
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue, CreateComment, SearchSC, LoadPagination, ConfirmSc, LoadPaginationResponsible
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
from kbds.user_kbds import USER_MENU_KEYBOARD
from services.user_private_service import base_start_handler, paginate_scs_logic, paginate_responsible_scs_logic
from utils.db_redis import redis_client
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

        # names.append({
        #     "filename": file_path.split("/")[-1],  # file_13.jpg
        #     "file": file_path  # photos/file_13.jpg
        # })

        files.append(file_path)

        await message.answer("Файл подготовлен к отправке")
        # return

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
        # await callback.message.answer(f"{e}")
        await callback.message.answer(f"При запросе в Итилиум произошла ошибка")
        return None

    await callback.answer()

    if response is None:
        return await callback.message.answer(f"Заявка с номером {sc_number} не найдена")

    logger.debug(f"find_sc_by_id | {response}")

    # Формируем текст сообщения
    message_text = Helpers.prepare_sc(response)

    btns: dict = {}

    if response["state"] != 'registered':
        # btn = get_callback_btns(
        #     btns={
        #         "Скрыть информацию ↩️": "del_message",
        #         # "Взять в работу ️ 🛠": "to_work{0}".format(sc_number),
        #     }
        # )
        btns["Скрыть информацию ↩️"] = "del_message"
    else:
        # btn = get_callback_btns(
        #     btns={
        #         "Скрыть информацию ↩️": "del_message",
        #     }
        # )
        btns["Скрыть информацию ↩️"] = "del_message"

    if response["new_state"]:
        btns["Поменять статус 🔁"] = f"show_state${sc_number}"
        # for state in response["new_state"]:
        #     btns[f"{state} ✏"] = f"change_{sc_number}_state_{state}"

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
        await callback.message.answer(f"При запросе в Итилиум произошла ошибка")
        return None

    btns: dict = {}

    if response["new_state"]:
        # btns["Поменять статус 🔁"] = f"show_state${sc_number}"
        btns["Назад ↩️"] = f"back_change_status${sc_number}"
        for state in response["new_state"]:
            btns[f"{state} ✏"] = f"ch_st_{sc_number}${state}"


    btn_keyboard = get_callback_btns(btns=btns, size=(1,2))

    # await bot.edit_message_text(
    #     text=callback.message.text,
    #     reply_markup=btn_keyboard
    # )

    await callback.message.edit_reply_markup(
        reply_markup=btn_keyboard
    )

    # await callback.message.answer(
    #     text=callback.message.text,
    #     reply_markup=btn_keyboard
    # )


@new_user_router.callback_query(StateFilter(None), F.data.startswith("back_change_status$"))
async def hide_sc_info_callback(callback: types.CallbackQuery):
    """
    Обработчик для скрытия статусов задачи
    """
    btns: dict = {}
    sc_number = callback.data[19:]
    await callback.answer()

    btn_keyboard = get_callback_btns(btns={
        "Скрыть информацию ↩️": "del_message",
        "Поменять статус 🔁": f"show_state${sc_number}",
    }, size=(1,))

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
    if new_state == "05_Отложено":
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
        btn_keyboard = get_callback_btns(btns={
            "Скрыть информацию ↩️": "del_message",
            "Поменять статус 🔁": f"show_state${sc_number}",
        }, size=(1,))

        response: dict | None = await ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc_number)
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
        text="Введите номер заявки для поиска или нажмите кнопку 'отмена'",
        reply_markup=get_callback_btns(btns={
            # "отмена": "cancel"
            "отмена ❌": "cancel"
        })
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
    looking_for = await message.answer("Ищу заявку с номером")
    state_data = await state.get_data()
    sc_number = message.text
    logger.debug(f"find sc by number {sc_number}")
    try:
        result: dict | None = await ItiliumBaseApi.find_sc_by_id(message.from_user.id, sc_number)
        logger.debug(f"find sc by number. response {sc_number}")
    except Exception as e:
        logger.debug(f"error for {message.from_user.id} {sc_number} {e}")
        await state.clear()
        await message.answer(f"Ошибка при поиске заявки {e}")
        await looking_for.delete()
        return

    if isinstance(result, str):
        await message.answer(f"Поиск заявки {sc_number}. {result}")
    else:
        await message.answer(
            text=Helpers.prepare_sc(result),
            parse_mode='HTML',
            reply_markup=get_callback_btns(
                btns={
                    "Скрыть информацию ↩️": "del_message",
                }
            )
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
    r = redis_client
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateScsDTO = PaginateScsDTO(
        redis=r,
        user_id=user_id,
    )

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not r.exists(user_id):
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {user_id} is not exist in Redis!")
        result: dict = await paginate_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = paginate_dto.get_cache_scs()
    else:
        scs = paginate_dto.get_cache_scs()

    data_with_pagination = await Helpers.get_paginated_kb_scs(scs)

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.answer(
        text="Ваши обращения",
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
    r = redis_client
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateScsDTO = PaginateScsDTO(
        redis=r,
        user_id=user_id,
    )

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not r.exists(user_id):
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {callback.from_user.id} is not exist in Redis!")
        result: dict = await paginate_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = paginate_dto.get_cache_scs()
        await state.clear()
    else:
        scs = paginate_dto.get_cache_scs()

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
    r = redis_client
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    paginate_dto: PaginateResponsibleScsDTO = PaginateResponsibleScsDTO(
        redis=r,
        user_id=user_id,
    )

    if is_loading:
        return

    if not r.exists(f"responsible:{str(user_id)}"):
        result: dict = await paginate_responsible_scs_logic(callback, paginate_dto)

        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = paginate_dto.get_cache_responsible_scs()
    else:
        scs = paginate_dto.get_cache_responsible_scs()

    data_with_pagination = await Helpers.get_paginated_kb_responsible_scs(scs)

    if send_message_for_search:
        await send_message_for_search.delete()

    await state.clear()

    await callback.message.answer(
        text="Обращения в вашей ответственности",
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
    r = redis_client
    user_id = callback.from_user.id
    scs = None
    send_message_for_search = None

    paginate_dto: PaginateResponsibleScsDTO = PaginateResponsibleScsDTO(
        redis=r,
        user_id=user_id,
    )

    state_data = await state.get_data()
    is_loading = state_data.get("load", None)
    await callback.answer()

    if is_loading:
        return

    if not r.exists(f"responsible:{str(user_id)}"):
        # Защищаем от повторного запроса
        await state.set_state(LoadPagination.load)
        await state.update_data(load=True)

        logger.debug(f"key with name {callback.from_user.id} is not exist in Redis!")
        result: dict = await paginate_responsible_scs_logic(callback, paginate_dto)
        send_message_for_search = result.get("send_message_for_search", None)

        # извлекаем из редиса
        scs = paginate_dto.get_cache_responsible_scs()
        await state.clear()
    else:
        scs = paginate_dto.get_cache_responsible_scs()

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
        # response = await ItiliumBaseApi.confirm_sc(
        #     telegram_user_id=callback.from_user.id,
        #     sc_number=sc_number,
        #     mark=mark,
        # )
        # logger.debug(f"confirm_sc response {response.status_code} | {response.text}")
        # if response.status_code == 200:
        #     await callback.message.edit_reply_markup(callback.id, reply_markup=None)
        await state.set_state(ConfirmSc.grade)
        await state.update_data(grade=mark, sc_number=sc_number, message_with_choice_grade=callback.message)
        await callback.message.answer(
            text=f"Ваша оценка: {mark}.",
            reply_markup=get_callback_btns(
                btns={
                    "отмена ❌": "cancel",
                    "добавить комментарий 📃": "add_confirm_sc_comment",
                    "отправить оценку 📩": "send_confirm_sc",
                }
            )
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
    # message_with_choice_grade: list = data.get("message_with_choice_grade")
    message_with_choice_grade: types.Message = data.get("message_with_choice_grade")

    await callback.answer()

    logger.debug(data)

    if grade in [0, 1, 2] and comment is None:
        await callback.message.delete()
        # await callback.message.answer(f"С оценкой ({grade}), комментарий обязателен!")
        message = await callback.message.answer(
            text=f"С оценкой ({grade}), комментарий обязателен!. \n"
                 f"Введите коментарий или отмените действия",
            reply_markup=get_callback_btns(
                btns={
                    "отмена ❌": "cancel",
                    "добавить комментарий 📃": "add_confirm_sc_comment",
                    "отправить оценку 📩": "send_confirm_sc",
                }
            )
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

    # if comment is not None:
    #     logger.debug(f"Ваш комментарий: {comment}")

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
        await callback.message.answer(text=f"Ваша оценка ({data["grade"]}) отправлена!")
    await state.clear()


@new_user_router.callback_query(StateFilter(ConfirmSc.grade), F.data.startswith("add_confirm_sc_comment"))
@new_user_router.callback_query(StateFilter(ConfirmSc.comment), F.data.startswith("add_confirm_sc_comment"))
async def set_comment_for_confirm_sc_handler(
        callback: types.CallbackQuery,
        state: FSMContext,
):
    logger.debug("Оставляем комментарий")
    await callback.answer()
    # await callback.message.delete()

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

    # await state.update_data(message_ids=message.append(message.message_id))
    await state.update_data(comment=comment)

    data: dict = await state.get_data()
    logger.debug(data)
    # проверяем если оценка 3,4,5, коментарий не обязателен и выводим кнопку отправить или добавить комментарий
    # проверяем если оценка 0,1,2, то комментарий обязателен


@new_user_router.callback_query()
async def btn_all_callback(callback: types.CallbackQuery):
    """
    Обработчик ловит любые Callback
    """
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
