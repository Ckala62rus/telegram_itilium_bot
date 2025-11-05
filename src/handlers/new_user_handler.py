import json
import logging
import re

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram_dialog import DialogManager, StartMode
from httpx import Response

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserButtonText
from dialogs.bot_menu.states import ChangeScStatus
from dialogs.bot_menu.calendar_states import CalendarDialog
from dto.paginate_scs_dto import PaginateScsDTO
from dto.paginate_scs_responsible_dto import PaginateResponsibleScsDTO
from dto.paginate_teams_dto import PaginateTeamsDTO
from dto.paginate_marketing_subdivisions_dto import PaginateMarketingSubdivisionsDTO
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue, CreateComment, SearchSC, LoadPagination, ConfirmSc, LoadPaginationResponsible
from fsm.marketing_fsm import MarketingRequest
from kbds.inline import get_callback_btns
from kbds.reply import get_keyboard
from kbds.user_kbds import USER_MENU_KEYBOARD
from services.user_private_service import base_start_handler, paginate_scs_logic, paginate_responsible_scs_logic, paginate_teams_logic
from utils.helpers import Helpers
from utils.message_templates import MessageTemplates, MessageFormatter, ButtonTemplates

new_user_router = Router()
new_user_router.message.filter(ChatTypeFilter(['private']))

logger = logging.getLogger(__name__)


# МАРКЕТИНГОВЫЕ ОБРАБОТЧИКИ - ВЫСОЧАЙШИЙ ПРИОРИТЕТ
@new_user_router.message(MarketingRequest.UPLOAD_FILES)
async def handle_marketing_file_upload(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка загрузки файлов для дизайна - ВЫСОЧАЙШИЙ ПРИОРИТЕТ"""
    # Строгая проверка состояния
    current_state = await state.get_state()
    if current_state != MarketingRequest.UPLOAD_FILES:
        logger.info(f"Not in UPLOAD_FILES state, current: {current_state}, ignoring")
        return
        
    logger.info(f"Marketing file upload handler triggered for user {message.from_user.id}")
    logger.info(f"Message type: photo={message.photo}, video={message.video}, document={message.document}, voice={message.voice}")
    try:
        # Проверяем, что это файл
        if not (message.photo or message.video or message.document or message.voice):
            logger.info(f"Not a file message, ignoring")
            return
            
        # Получаем информацию о файле
        logger.info(f"Getting file info for user {message.from_user.id}")
        file_path = await Helpers.get_file_info(message, bot)
        logger.info(f"File path received: {file_path}")
        
        # Получаем оригинальное имя файла
        original_filename = "Неизвестный файл"
        if message.document:
            original_filename = message.document.file_name or "Документ"
        elif message.photo:
            original_filename = f"Фото_{len(message.photo)}"
        elif message.video:
            original_filename = message.video.file_name or "Видео"
        elif message.voice:
            original_filename = "Голосовое сообщение"
        
        # Получаем текущий список файлов
        data = await state.get_data()
        files = data.get("uploaded_files", [])
        file_names = data.get("uploaded_file_names", [])
        
        # Добавляем новый файл и его имя
        files.append(file_path)
        file_names.append(original_filename)
        
        # Сохраняем обновленный список
        await state.update_data(uploaded_files=files, uploaded_file_names=file_names)
        
        # Получаем ID предыдущего сообщения с кнопками (если есть)
        data = await state.get_data()
        old_message_id = data.get("file_upload_message_id")
        
        # Удаляем старое сообщение с кнопками, если оно есть
        if old_message_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=old_message_id)
                logger.info(f"Deleted old file upload message {old_message_id}")
            except Exception as e:
                logger.warning(f"Could not delete old message {old_message_id}: {e}")
        
        # Отправляем одно объединенное сообщение с обновленной информацией и кнопками
        sent_message = await message.answer(
            text=f"📁 **Загрузка файлов для дизайна**\n\n"
                 f"✅ Файл успешно добавлен! Загружено файлов: {len(files)}\n\n"
                 "Если хотите добавить еще файлы, можете продолжить загрузку.\n"
                 "Или нажмите 'Далее' для перехода к следующему шагу.",
            reply_markup=get_callback_btns(
                btns={
                    "🔙 Назад к меню": "back_to_files",
                    "❌ Отмена": "cancel_marketing"
                },
                size=(1, 1)
            )
        )
        
        # Сохраняем ID нового сообщения для возможного удаления в будущем
        await state.update_data(file_upload_message_id=sent_message.message_id)
        
        # Обновляем данные в FSM для корректного отображения в других обработчиках
        await state.update_data(uploaded_files=files)
        
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await message.answer("❌ Ошибка при загрузке файла. Попробуйте еще раз.")


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
    Метод инициирует создание нового обращения с проверкой прав на маркетинговые заявки.
    """
    logger.debug("Perform callback command create_new_issue")
    await callback.answer()
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔄 Загружаю... подождите")
    
    try:
        # Получаем данные пользователя для проверки прав
        user_data = await ItiliumBaseApi.get_employee_data_by_identifier(callback)
        
        # Удаляем индикатор загрузки
        await loading_msg.delete()
        
        if user_data and user_data.get('canCreateMarketingRequests', False):
            # Пользователь может создавать маркетинговые заявки
            await callback.message.answer(
                text="Выберите тип заявки:",
                reply_markup=get_callback_btns(
                    btns={
                        "Заявка в отдел ИТ": "create_regular_issue",
                        "Заявка в отдел маркетинга": "create_marketing_issue",
                        "❌ Отмена": "cancel_marketing"
                    },
                    size=(1, 1, 1)
                )
            )
            await state.set_state(MarketingRequest.CHOOSE_REQUEST_TYPE)
        else:
            # Обычная логика создания заявки
            await callback.message.answer(
                text=MessageTemplates.ENTER_ISSUE_DESCRIPTION,
                reply_markup=get_keyboard(str(UserButtonText.CANCEL))
            )
            await state.set_state(CreateNewIssue.description)
            await state.update_data(description="")
            await state.update_data(files=[])
            
    except Exception as e:
        await loading_msg.delete()
        
        # Сбрасываем FSM состояние при ошибке
        await state.clear()
        
        # Показываем единое сообщение об ошибке от Итилиума и не отображаем кнопки отмены/повтора
        from utils.message_templates import MessageTemplates
        await callback.message.answer(
            text=MessageTemplates.ITILIUM_EMPTY_RESPONSE,
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        await state.clear()
        logger.error(f"Error loading user data: {e}")


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
    
    try:
        user_data_from_itilium: dict | None = await ItiliumBaseApi.get_employee_data_by_identifier(message)
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        await state.clear()
        from utils.message_templates import MessageTemplates
        await message.answer(
            text=MessageTemplates.ITILIUM_EMPTY_RESPONSE,
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    if user_data_from_itilium is None:
        logger.debug("user not found in Itilium")
        await state.clear()
        await message.answer(
            text="Не удалось найти вас в системе ITILIUM",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    # send data to itilium api for create issue
    # Показать индикатор отправки и убрать клавиатуру с кнопками
    loading_msg = await message.answer(
        "⏳ Отправляю заявку...",
        reply_markup=types.ReplyKeyboardRemove()
    )
    try:
        response: Response = await ItiliumBaseApi.create_new_sc({
            "UUID": user_data_from_itilium["UUID"],
            "Description": data["description"],
            "shortDescription": Helpers.prepare_short_description_for_sc(data["description"]),
        }, data["files"])

        logger.debug(f"{response.status_code} | {response.text}")

        if response.status_code in (httpx.codes.OK, httpx.codes.CREATED, httpx.codes.NO_CONTENT):
            # Удаляем служебное сообщение "Отправляю заявку..." и отправляем новое об успехе
            try:
                await loading_msg.delete()
            except Exception:
                pass
            await message.answer("✅ Заявка успешно создана!")
        else:
            logger.debug(f"{response.text}")
            try:
                await loading_msg.delete()
            except Exception:
                pass
            await message.answer(
                text="❌ Не удалось создать заявку. Проблемы на стороне Итилиума. Обратитесь к администратору."
            )
    except Exception as e:
        logger.exception(e)
        try:
            await loading_msg.delete()
        except Exception:
            pass
        await message.answer("❌ Не удалось создать заявку. Проблемы на стороне Итилиума. Обратитесь к администратору.")

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
    # Исключаем маркетинговые заявки
    if await state.get_state() == MarketingRequest.UPLOAD_FILES:
        return
        
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
    # Исключаем маркетинговые заявки
    if await state.get_state() == MarketingRequest.UPLOAD_FILES:
        return
    
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
    # Исключаем маркетинговые заявки
    current_state = await state.get_state()
    if current_state == MarketingRequest.UPLOAD_FILES:
        logger.info(f"Excluding marketing file upload from test_filter, state: {current_state}")
        return
    
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




@new_user_router.message(Command("calendar"))
@new_user_router.message(F.text == "📅 Календарь")
async def start_calendar_dialog(message: types.Message, dialog_manager: DialogManager):
    """Запуск диалога с календарем"""
    await dialog_manager.start(CalendarDialog.MAIN, mode=StartMode.RESET_STACK)


@new_user_router.callback_query(F.data == "calendar")
async def calendar_callback(callback: types.CallbackQuery, dialog_manager: DialogManager):
    """Обработчик callback кнопки календаря"""
    await callback.answer()
    await dialog_manager.start(CalendarDialog.MAIN, mode=StartMode.RESET_STACK)


# ========== ОБРАБОТЧИКИ МАРКЕТИНГОВЫХ ЗАЯВОК ==========

@new_user_router.callback_query(F.data == "create_regular_issue")
async def create_regular_issue_callback(callback: types.CallbackQuery, state: FSMContext):
    """Переход к созданию обычной заявки"""
    await callback.answer()
    await callback.message.answer(
        text=MessageTemplates.ENTER_ISSUE_DESCRIPTION,
        reply_markup=get_keyboard(str(UserButtonText.CANCEL))
    )
    await state.set_state(CreateNewIssue.description)
    await state.update_data(description="")
    await state.update_data(files=[])


@new_user_router.callback_query(F.data == "create_marketing_issue")
async def start_marketing_request_callback(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания маркетинговой заявки"""
    await callback.answer()
    logger.info(f"Starting marketing request for user {callback.from_user.id}")
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔄 Загружаю... подождите")
    
    try:
        # Получаем список сервисов
        services = await ItiliumBaseApi.get_marketing_services(callback.from_user.id)
        logger.info(f"Received {len(services) if services else 0} marketing services")
        
        if not services:
            await loading_msg.delete()
            await callback.message.answer("Ошибка получения списка сервисов. Попробуйте позже.")
            await state.clear()
            return
            
    except Exception as e:
        logger.error(f"Error getting marketing services: {e}")
        await loading_msg.delete()
        await callback.message.answer(
            "❌ Ошибка подключения к серверу. Попробуйте еще раз.",
            reply_markup=get_callback_btns(
                btns={"🔄 Попробовать снова": "create_marketing_issue", "❌ Отмена": "cancel_marketing"},
                size=(1, 1)
            )
        )
        await state.clear()
        return
    
    # Удаляем индикатор загрузки
    await loading_msg.delete()
    
    # Создаем inline кнопки для сервисов с эмодзи
    # Используем индекс вместо полного названия, чтобы избежать превышения лимита callback_data (64 байта)
    service_emojis = {
        "Дизайн": "🎨",
        "Мероприятие": "🎉", 
        "Реклама": "📢",
        "SMM": "📱",
        "Акция": "🏷️",
        "Иное": "📋"
    }
    
    service_buttons = {}
    for index, service in enumerate(services):
        service_name = service["КомпонентаУслуги"]
        emoji = service_emojis.get(service_name, "📋")
        # Используем индекс для callback_data, чтобы избежать превышения лимита 64 байта
        service_buttons[f"{emoji} {service_name}"] = f"select_service_{index}"
    service_buttons["🔙 Назад"] = "back_to_request_type"
    service_buttons["❌ Отмена"] = "cancel_marketing"
    
    logger.info(f"Sending service selection message with {len(service_buttons)} buttons")
    await callback.message.answer(
        text="Выберите сервис маркетинга:",
        reply_markup=get_callback_btns(btns=service_buttons, size=(1,))
    )
    
    # Сохраняем сервисы в состоянии и ID сообщения
    await state.update_data(services=services, current_message_id=callback.message.message_id)
    await state.set_state(MarketingRequest.CHOOSE_SERVICE)
    logger.info(f"Marketing request state set to CHOOSE_SERVICE")


@new_user_router.callback_query(F.data.startswith("select_service_"))
async def choose_service_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора сервиса"""
    await callback.answer()
    
    # Извлекаем индекс сервиса из callback data
    try:
        service_index = int(callback.data.replace("select_service_", ""))
    except ValueError:
        await callback.message.answer("Ошибка выбора сервиса. Попробуйте еще раз.")
        return
    
    data = await state.get_data()
    services = data.get("services", [])
    
    # Находим выбранный сервис по индексу
    if service_index < 0 or service_index >= len(services):
        await callback.message.answer("Сервис не найден. Попробуйте еще раз.")
        return
    
    selected_service = services[service_index]
    
    # Сохраняем выбранный сервис
    await state.update_data(selected_service=selected_service)
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔄 Загружаю подразделения... подождите")
    
    try:
        # Получаем список подразделений
        logger.info(f"Loading subdivisions for user {callback.from_user.id}")
        subdivisions = await ItiliumBaseApi.get_marketing_subdivisions(callback.from_user.id)
        logger.info(f"Received subdivisions: {subdivisions}")
        
        if not subdivisions:
            await loading_msg.delete()
            logger.error(f"No subdivisions received for user {callback.from_user.id}")
            await callback.message.answer("Ошибка получения списка подразделений. Попробуйте позже.")
            await state.clear()
            return
        
        # Удаляем индикатор загрузки
        await loading_msg.delete()
        
        # Создаем DTO для пагинации
        paginate_dto = PaginateMarketingSubdivisionsDTO(user_id=callback.from_user.id)
        await paginate_dto.set_cache_subdivisions(subdivisions)
        
        # Создаем пагинированную клавиатуру
        paginated_keyboard = await Helpers.get_paginated_kb_marketing_subdivisions(subdivisions, page=0)
        
        # Редактируем существующее сообщение вместо создания нового
        await callback.message.edit_text(
            text="Выберите подразделение:",
            reply_markup=paginated_keyboard
        )
        
        # Сохраняем подразделения в состоянии
        await state.update_data(subdivisions=subdivisions)
        await state.set_state(MarketingRequest.CHOOSE_SUBDIVISION)
        
    except Exception as e:
        await loading_msg.delete()
        await callback.message.answer("Произошла ошибка при загрузке подразделений. Попробуйте позже.")
        await state.clear()
        logger.error(f"Error loading marketing subdivisions: {e}")


@new_user_router.callback_query(F.data.startswith("subdivisions_page_"))
async def subdivisions_pagination_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик пагинации подразделений"""
    await callback.answer()
    
    data = await state.get_data()
    subdivisions = data.get("subdivisions", [])
    
    if not subdivisions:
        await callback.message.answer("Список подразделений не найден. Попробуйте еще раз.")
        return
    
    # Извлекаем номер страницы
    try:
        page = int(callback.data.replace("subdivisions_page_", ""))
    except ValueError:
        await callback.message.answer("Ошибка пагинации. Попробуйте еще раз.")
        return
    
    # Создаем пагинированную клавиатуру
    paginated_keyboard = await Helpers.get_paginated_kb_marketing_subdivisions(subdivisions, page=page)
    
    await callback.message.edit_reply_markup(reply_markup=paginated_keyboard)


@new_user_router.callback_query(F.data.startswith("select_sub_"))
async def choose_subdivision_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора подразделения"""
    await callback.answer()
    
    # Извлекаем индекс подразделения из callback data
    try:
        subdivision_index = int(callback.data.replace("select_sub_", ""))
    except ValueError:
        await callback.message.answer("Ошибка выбора подразделения. Попробуйте еще раз.")
        return
    
    data = await state.get_data()
    subdivisions = data.get("subdivisions", [])
    
    # Проверяем, что индекс валидный
    if subdivision_index >= len(subdivisions):
        await callback.message.answer("Подразделение не найдено. Попробуйте еще раз.")
        return
    
    # Получаем название подразделения по индексу
    subdivision_name = subdivisions[subdivision_index]
    
    # Сохраняем выбранное подразделение (это строка)
    await state.update_data(selected_subdivision=subdivision_name)
    
    # Переходим к выбору даты исполнения через календарь
    await callback.message.edit_text(
        text="📅 **Дата исполнения (обязательное поле)**\n\nВыберите дату из календаря:",
        reply_markup=get_callback_btns(
            btns={
                "📅 Выбрать дату": "choose_date_calendar",
                "🔙 Назад": "back_to_subdivisions",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1, 1)
        )
    )
    await state.set_state(MarketingRequest.CHOOSE_EXECUTION_DATE)








@new_user_router.callback_query(F.data == "choose_date_calendar")
async def choose_date_with_calendar_callback(callback: types.CallbackQuery, dialog_manager: DialogManager, state: FSMContext):
    """Запуск календаря для выбора даты"""
    await callback.answer()
    try:
        from dialogs.bot_menu.states import ChangeScStatus
        
        # Запускаем календарь для маркетинговых заявок
        from dialogs.bot_menu.states import MarketingCalendar
        await dialog_manager.start(
            state=MarketingCalendar.select_date,
            data={
                "marketing_request": True,
                "user_id": callback.from_user.id,
                "callback_message_id": callback.message.message_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting calendar: {e}")
        await callback.message.edit_text("Ошибка запуска календаря. Попробуйте еще раз.")


# Обработчик для завершения календаря в контексте маркетинговых заявок
@new_user_router.callback_query(F.data.startswith("marketing_calendar_done_"))
async def handle_marketing_calendar_done(callback: types.CallbackQuery, state: FSMContext):
    """Обработка завершения календаря для маркетинговых заявок"""
    await callback.answer()
    
    # Извлекаем дату из callback data
    date_str = callback.data.replace("marketing_calendar_done_", "")
    try:
        from datetime import datetime
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        await callback.message.edit_text("Ошибка формата даты. Попробуйте еще раз.")
        return
    
    # Проверяем, что дата не в прошлом
    from datetime import date
    today = date.today()
    if selected_date < today:
        await callback.message.edit_text("❌ Дата не может быть в прошлом. Выберите другую дату.")
        return
    
    # Сохраняем дату в FSM
    await state.update_data(execution_date=selected_date)
    
    # Обновляем сообщение и переходим к форме
    await callback.message.edit_text(f"✅ Дата исполнения: {selected_date.strftime('%d.%m.%Y')}")
    await proceed_to_form(callback, state)




# Обработчики кнопок "Назад"
@new_user_router.callback_query(F.data == "back_to_request_type")
async def back_to_request_type_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору типа заявки"""
    await callback.answer()
    await callback.message.edit_text(
        text="Выберите тип заявки:",
        reply_markup=get_callback_btns(
            btns={
                "Заявка в отдел ИТ": "create_regular_issue",
                "Заявка в отдел маркетинга": "create_marketing_issue",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1, 1)
        )
    )
    await state.set_state(MarketingRequest.CHOOSE_REQUEST_TYPE)


@new_user_router.callback_query(F.data == "back_to_services")
async def back_to_services_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору сервиса"""
    await callback.answer()
    
    data = await state.get_data()
    services = data.get("services", [])
    
    if not services:
        await callback.message.answer("Ошибка: данные сервисов не найдены. Попробуйте еще раз.")
        await state.clear()
        return
    
    # Создаем inline кнопки для сервисов с эмодзи
    service_emojis = {
        "Дизайн": "🎨",
        "Мероприятие": "🎉", 
        "Реклама": "📢",
        "SMM": "📱",
        "Акция": "🏷️",
        "Иное": "📋"
    }
    
    service_buttons = {}
    for service in services:
        service_name = service["КомпонентаУслуги"]
        emoji = service_emojis.get(service_name, "📋")
        service_buttons[f"{emoji} {service_name}"] = f"select_service_{service_name}"
    service_buttons["🔙 Назад"] = "back_to_request_type"
    service_buttons["❌ Отмена"] = "cancel_marketing"
    
    await callback.message.edit_text(
        text="Выберите сервис маркетинга:",
        reply_markup=get_callback_btns(btns=service_buttons, size=(1,))
    )
    await state.set_state(MarketingRequest.CHOOSE_SERVICE)


@new_user_router.callback_query(F.data == "back_to_subdivisions")
async def back_to_subdivisions_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору подразделения"""
    await callback.answer()
    
    data = await state.get_data()
    subdivisions = data.get("subdivisions", [])
    
    if not subdivisions:
        await callback.message.answer("Ошибка: данные подразделений не найдены. Попробуйте еще раз.")
        await state.clear()
        return
    
    # Создаем пагинированную клавиатуру
    paginated_keyboard = await Helpers.get_paginated_kb_marketing_subdivisions(subdivisions, page=0)
    
    await callback.message.edit_text(
        text="Выберите подразделение:",
        reply_markup=paginated_keyboard
    )
    await state.set_state(MarketingRequest.CHOOSE_SUBDIVISION)






@new_user_router.callback_query(F.data == "cancel_marketing")
async def cancel_marketing_request_callback(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await callback.answer()
    await callback.message.answer("Создание заявки отменено.")
    await state.clear()


async def proceed_to_form(callback_or_message, state: FSMContext):
    """Переход к заполнению формы в зависимости от номера формы"""
    data = await state.get_data()
    selected_service = data.get("selected_service", {})
    form_number = selected_service.get("НомерФормы", 3)
    
    logger.info(f"proceed_to_form: selected_service = {selected_service}")
    logger.info(f"proceed_to_form: form_number = {form_number}")
    
    # Определяем, что у нас - callback или message
    if hasattr(callback_or_message, 'message'):
        # Это callback
        message = callback_or_message.message
    else:
        # Это message
        message = callback_or_message
    
    logger.info(f"proceed_to_form: Processing form_number = {form_number}")
    
    if form_number == 1:
        logger.info("proceed_to_form: Entering form 1 (Design) logic")
        # Форма для дизайна - сначала заполняем форму, потом файлы
        await message.edit_text(
            text="Введите название макета (баннер, афиша):",
            reply_markup=get_callback_btns(
                btns={"❌ Отмена": "cancel_marketing"},
                size=(1,)
            )
        )
        await state.set_state(MarketingRequest.FILL_FORM_1)
    elif form_number == 2:
        # Форма для мероприятия
        await message.edit_text(
            text="Введите тему мероприятия:",
            reply_markup=get_callback_btns(
                btns={"❌ Отмена": "cancel_marketing"},
                size=(1,)
            )
        )
        await state.set_state(MarketingRequest.FILL_FORM_2)
    else:
        # Форма для рекламы, SMM, акций, иного
        await message.edit_text(
            text="Введите описание заявки:",
            reply_markup=get_callback_btns(
                btns={"❌ Отмена": "cancel_marketing"},
                size=(1,)
            )
        )
        await state.set_state(MarketingRequest.FILL_FORM_3)




@new_user_router.callback_query(F.data == "add_file")
async def add_file_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Добавить файл'"""
    await callback.answer()
    data = await state.get_data()
    files = data.get("uploaded_files", [])
    
    logger.info(f"Add file callback - current files count: {len(files)}")
    
    await callback.message.edit_text(
        text=f"📁 **Добавление файла**\n\n"
             f"✅ Загружено файлов: {len(files)}\n\n"
             "Прикрепите файл к сообщению (фото, документ, видео, голосовое сообщение):\n"
             "• Можно прикрепить несколько файлов\n"
             "• Поддерживаются: фото, документы, видео",
        reply_markup=get_callback_btns(
            btns={
                "🔙 Назад к меню": "back_to_files",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1)
        )
    )
    
    # Сохраняем ID сообщения для возможного удаления
    await state.update_data(file_upload_message_id=callback.message.message_id)


@new_user_router.callback_query(F.data == "clear_files")
async def clear_files_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Удалить файлы'"""
    await callback.answer()
    await state.update_data(uploaded_files=[])
    await callback.message.edit_text(
        text="📁 **Загрузка файлов для дизайна**\n\n"
             "✅ Файлы удалены\n\n"
             "Прикрепите файлы макета (изображения, документы):\n"
             "• Можно прикрепить несколько файлов\n"
             "• Поддерживаются: фото, документы, видео\n\n"
             "После загрузки файлов нажмите 'Далее'",
        reply_markup=get_callback_btns(
            btns={
                "📁 Добавить файл": "add_file",
                "➡️ Далее": "proceed_to_preview",
                "🔙 Назад": "back_to_date_selection",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1, 1, 1)
        )
    )


@new_user_router.callback_query(F.data == "back_to_files")
async def back_to_files_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к загрузке файлов"""
    await callback.answer()
    data = await state.get_data()
    files = data.get("uploaded_files", [])
    
    logger.info(f"Back to files callback - current files count: {len(files)}")
    
    await callback.message.edit_text(
        text=f"📁 **Загрузка файлов для дизайна**\n\n"
             f"✅ Загружено файлов: {len(files)}\n\n"
             "Прикрепите файлы макета (изображения, документы):\n"
             "• Можно прикрепить несколько файлов\n"
             "• Поддерживаются: фото, документы, видео\n\n"
             "После загрузки файлов нажмите 'Далее'",
        reply_markup=get_callback_btns(
            btns={
                "📁 Добавить файл": "add_file",
                "🗑️ Удалить файлы": "clear_files" if files else "add_file",
                "➡️ Далее": "proceed_to_preview",
                "🔙 Назад": "back_to_date_selection",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1, 1, 1, 1)
        )
    )


@new_user_router.callback_query(F.data == "proceed_to_preview")
async def proceed_to_preview_callback(callback: types.CallbackQuery, state: FSMContext):
    """Переход к предварительному просмотру"""
    await callback.answer()
    await show_preview(callback.message, state)


@new_user_router.callback_query(F.data == "back_to_subdivisions_from_date")
async def back_to_subdivisions_from_date_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору подразделения из выбора даты"""
    await callback.answer()
    
    # Получаем данные из FSM
    data = await state.get_data()
    current_message_id = data.get("current_message_id")
    
    # Показываем индикатор загрузки
    loading_msg = await callback.message.answer("🔄 Загружаю подразделения...")
    
    try:
        # Получаем список подразделений из кеша
        subdivisions_dto = PaginateMarketingSubdivisionsDTO(callback.from_user.id)
        subdivisions = await subdivisions_dto.get_cache_subdivisions()
        
        # Если кеш пустой, загружаем заново
        if not subdivisions:
            logger.info(f"Cache empty for user {callback.from_user.id}, reloading subdivisions")
            subdivisions = await ItiliumBaseApi.get_marketing_subdivisions(callback.from_user.id)
            
            if not subdivisions:
                await loading_msg.delete()
                await callback.message.edit_text("Ошибка получения списка подразделений. Попробуйте позже.")
                await state.clear()
                return
            
            # Сохраняем в кеш
            await subdivisions_dto.set_cache_subdivisions(subdivisions)
        
        # Удаляем индикатор загрузки
        await loading_msg.delete()
        
        # Создаем клавиатуру для выбора подразделения
        keyboard = await Helpers.get_paginated_kb_marketing_subdivisions(subdivisions, page=0)
        
        await callback.message.edit_text(
            text="Выберите подразделение:",
            reply_markup=keyboard
        )
        
        await state.set_state(MarketingRequest.CHOOSE_SUBDIVISION)
        logger.info(f"User {callback.from_user.id} returned to CHOOSE_SUBDIVISION from date selection")
        
    except Exception as e:
        await loading_msg.delete()
        logger.error(f"Error loading subdivisions for user {callback.from_user.id}: {e}")
        await callback.message.edit_text("Ошибка загрузки подразделений. Попробуйте позже.")
        await state.clear()


# Обработчики отмены для всех состояний маркетинговых заявок
@new_user_router.message(StateFilter(MarketingRequest.CHOOSE_REQUEST_TYPE), F.text == "Отмена")
async def cancel_marketing_request_type(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(StateFilter(MarketingRequest.CHOOSE_SERVICE), F.text == "Отмена")
async def cancel_marketing_request_service(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(StateFilter(MarketingRequest.CHOOSE_SUBDIVISION), F.text == "Отмена")
async def cancel_marketing_request_subdivision(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(StateFilter(MarketingRequest.CHOOSE_EXECUTION_DATE), F.text == "Отмена")
async def cancel_marketing_request_date(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(MarketingRequest.CHOOSE_EXECUTION_DATE, F.text != "Отмена")
async def handle_date_input(message: types.Message, state: FSMContext):
    """Обработка ввода даты пользователем"""
    date_text = message.text.strip()
    
    try:
        from datetime import datetime
        # Пробуем разные форматы даты
        for date_format in ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%y", "%d/%m/%y", "%d-%m-%y"]:
            try:
                selected_date = datetime.strptime(date_text, date_format).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неверный формат даты")
        
        # Проверяем, что дата не в прошлом
        from datetime import date
        today = date.today()
        if selected_date < today:
            await message.answer("❌ Дата не может быть в прошлом. Введите корректную дату:")
            return
        
        # Сохраняем выбранную дату
        await state.update_data(execution_date=selected_date)
        
        # Переходим к заполнению формы
        await message.answer(f"✅ Дата исполнения: {selected_date.strftime('%d.%m.%Y')}")
        await proceed_to_form(message, state)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ (например: 25.12.2024):"
        )




@new_user_router.message(StateFilter(MarketingRequest.FILL_FORM_1), F.text == "Отмена")
async def cancel_marketing_request_form1(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(StateFilter(MarketingRequest.FILL_FORM_2), F.text == "Отмена")
async def cancel_marketing_request_form2(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


@new_user_router.message(StateFilter(MarketingRequest.FILL_FORM_3), F.text == "Отмена")
async def cancel_marketing_request_form3(message: types.Message, state: FSMContext):
    """Отмена создания маркетинговой заявки"""
    await message.answer("Создание заявки отменено.")
    await state.clear()


# Обработчики заполнения форм
@new_user_router.message(MarketingRequest.FILL_FORM_1, F.text != "Отмена")
async def fill_form_1_design(message: types.Message, state: FSMContext):
    """Заполнение формы для дизайна"""
    logger.info(f"Обработка сообщения в fill_form_1_design: {message.text}")
    data = await state.get_data()
    form_data = data.get("form_data", {})
    logger.info(f"Текущие данные формы: {form_data}")
    
    if "layout_name" not in form_data:
        form_data["layout_name"] = message.text
        await state.update_data(form_data=form_data)
        logger.info("Запрошены размеры")
        await message.answer("Введите размеры (в мм или dpi):")
    elif "dimensions" not in form_data:
        form_data["dimensions"] = message.text
        await state.update_data(form_data=form_data)
        logger.info("Запрошено назначение")
        await message.answer("Для чего: - печать - WEB-версия:")
    elif "purpose" not in form_data:
        form_data["purpose"] = message.text
        await state.update_data(form_data=form_data)
        logger.info("Запрошен обязательный текст")
        await message.answer("Введите обязательный текст:")
    elif "required_text" not in form_data:
        form_data["required_text"] = message.text
        await state.update_data(form_data=form_data)
        logger.info("Запрошены форматы предоставления макета")
        await message.answer("Введите форматы предоставления макета (pdf, png, psd, tiff, crd):")
        await state.set_state(MarketingRequest.FILL_LAYOUT_FORMATS)


@new_user_router.message(MarketingRequest.FILL_LAYOUT_FORMATS, F.text != "Отмена")
async def fill_layout_formats(message: types.Message, state: FSMContext):
    """Заполнение форматов предоставления макета"""
    logger.info(f"Обработка сообщения в fill_layout_formats: {message.text}")
    data = await state.get_data()
    form_data = data.get("form_data", {})
    
    # Сохраняем форматы
    form_data["formats"] = message.text
    await state.update_data(form_data=form_data)
    
    # Логируем переход к загрузке файлов
    logger.info(f"Переход к загрузке файлов для дизайна. Все поля формы заполнены.")
    
    # Переходим к загрузке файлов (согласно ТЗ - файлы загружаются после заполнения всех полей)
    await message.answer(
        text="📁 **Загрузка файлов макета**\n\n"
             "Прикрепите файлы макета:\n"
             "• Можно прикрепить несколько файлов\n"
             "• Поддерживаются: фото, документы, видео\n\n"
             "После загрузки файлов нажмите 'Далее'",
        reply_markup=get_callback_btns(
            btns={
                "📁 Добавить файл": "add_file",
                "➡️ Далее": "proceed_to_preview",
                "🔙 Назад": "back_to_date_selection",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1, 1, 1)
        )
    )
    await state.set_state(MarketingRequest.UPLOAD_FILES)
    logger.info(f"Состояние изменено на UPLOAD_FILES")


@new_user_router.message(MarketingRequest.FILL_FORM_2, F.text != "Отмена")
async def fill_form_2_event(message: types.Message, state: FSMContext):
    """Заполнение формы для мероприятия"""
    data = await state.get_data()
    form_data = data.get("form_data", {})
    
    if "event_theme" not in form_data:
        form_data["event_theme"] = message.text
        await state.update_data(form_data=form_data)
        await message.answer("Введите описание мероприятия:")
    elif "event_description" not in form_data:
        form_data["event_description"] = message.text
        await state.update_data(form_data=form_data)
        await message.answer("Введите бюджет:")
    elif "event_budget" not in form_data:
        form_data["event_budget"] = message.text
        await state.update_data(form_data=form_data)
        await message.answer("Свободное поле для заполнения:")
    elif "event_free_field" not in form_data:
        form_data["event_free_field"] = message.text
        await state.update_data(form_data=form_data)
        await show_preview(message, state)


@new_user_router.message(MarketingRequest.FILL_FORM_3, F.text != "Отмена")
async def fill_form_3_other(message: types.Message, state: FSMContext):
    """Заполнение формы для рекламы, SMM, акций и прочего"""
    data = await state.get_data()
    form_data = data.get("form_data", {})
    
    # Для формы 3 только одно свободное поле
    form_data["free_text"] = message.text
    await state.update_data(form_data=form_data)
    await show_preview(message, state)


async def show_preview(message: types.Message, state: FSMContext):
    """Показ предварительного просмотра заявки"""
    logger.info(f"Starting show_preview for user {message.from_user.id}")
    data = await state.get_data()
    logger.info(f"FSM data: {data}")
    
    selected_service = data.get("selected_service", {})
    selected_subdivision = data.get("selected_subdivision", {})
    execution_date = data.get("execution_date")
    form_data = data.get("form_data", {})
    
    logger.info(f"Selected service: {selected_service}")
    logger.info(f"Selected subdivision: {selected_subdivision}")
    logger.info(f"Execution date: {execution_date}")
    logger.info(f"Form data: {form_data}")
    
    # Первое сообщение - основная информация
    basic_info = f"📋 **Предварительный просмотр заявки**\n\n"
    basic_info += f"**Сервис:** {selected_service.get('КомпонентаУслуги', 'Не выбран')}\n"
    basic_info += f"**Подразделение:** {selected_subdivision if selected_subdivision else 'Не выбрано'}\n"
    basic_info += f"**Дата исполнения:** {execution_date.strftime('%d.%m.%Y') if execution_date else 'Не указана'}\n"
    
    await message.answer(text=basic_info)
    
    # Второе сообщение - данные формы
    form_number = selected_service.get("НомерФормы", 3)
    if form_number == 1:  # Дизайн
        form_info = "**📝 Данные формы (Дизайн):**\n"
        form_info += f"**Название макета:** {form_data.get('layout_name', 'Не указано')}\n"
        form_info += f"**Размеры:** {form_data.get('dimensions', 'Не указаны')}\n"
        form_info += f"**Назначение:** {form_data.get('purpose', 'Не указано')}\n"
        form_info += f"**Обязательный текст:** {form_data.get('required_text', 'Не указан')}\n"
        form_info += f"**Форматы:** {form_data.get('formats', 'Не указаны')}\n"
            
        await message.answer(text=form_info)
        
        # Третье сообщение - файлы
        uploaded_files = data.get("uploaded_files", [])
        uploaded_file_names = data.get("uploaded_file_names", [])
        if uploaded_files:
            files_info = f"**📁 Загружено файлов:** {len(uploaded_files)}\n"
            for i, file_name in enumerate(uploaded_file_names, 1):
                files_info += f"  {i}. {file_name}\n"
        else:
            files_info = "**📁 Файлы:** Не загружены\n"
            
        await message.answer(text=files_info)
        
    elif form_number == 2:  # Мероприятие
        form_info = "**📝 Данные формы (Мероприятие):**\n"
        form_info += f"**Тема мероприятия:** {form_data.get('event_theme', 'Не указана')}\n"
        form_info += f"**Описание:** {form_data.get('event_description', 'Не указано')}\n"
        form_info += f"**Бюджет:** {form_data.get('event_budget', 'Не указан')}\n"
        if form_data.get('event_free_field'):
            form_info += f"**Дополнительно:** {form_data.get('event_free_field', '')}\n"
            
        await message.answer(text=form_info)
        
    else:  # Реклама, SMM, Акция, Иное
        # form_info = "**📝 Данные формы:**\n"
        form_info = f"**Описание:** {form_data.get('free_text', 'Не указано')}\n"
            
        await message.answer(text=form_info)
    
    # Последнее сообщение с кнопками: отправляем напрямую без дополнительного подтверждения
    await message.answer(
        text="**Выберите действие:**",
        reply_markup=get_callback_btns(
            btns={
                "✅ Отправить заявку": "finalize_request",
                "❌ Отмена": "cancel_marketing"
            },
            size=(1, 1)
        )
    )
    await state.set_state(MarketingRequest.PREVIEW_REQUEST)


@new_user_router.callback_query(F.data == "confirm_create_request")
async def confirm_create_request_callback(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение создания заявки"""
    await callback.answer()
    await callback.message.edit_text(
        text="Отправить заявку?",
        reply_markup=get_callback_btns(
            btns={
                "✅ Да": "finalize_request",
                "❌ Нет": "back_to_preview",
                "🚫 Отмена": "cancel_marketing"
            },
            size=(1, 1, 1)
        )
    )
    await state.set_state(MarketingRequest.CONFIRM_REQUEST)


@new_user_router.callback_query(F.data == "finalize_request")
async def finalize_request_callback(callback: types.CallbackQuery, state: FSMContext):
    """Финальное создание заявки"""
    await callback.answer()
    data = await state.get_data()

    # Показываем индикатор отправки и убираем кнопки
    try:
        await callback.message.edit_text("⏳ Отправляю заявку...")
    except Exception:
        pass
    
    # Формируем JSON для логирования
    uploaded_files = data.get("uploaded_files", [])
    uploaded_file_names = data.get("uploaded_file_names", [])
    
    # Создаем список файлов с именами и путями (формат как в create_new_sc)
    files_with_names = []
    for i, file_path in enumerate(uploaded_files):
        filename = uploaded_file_names[i] if i < len(uploaded_file_names) else f"Файл_{i+1}"
        files_with_names.append({
            "filename": filename,
            "path": file_path
        })
    
    request_data = {
        "service": data.get("selected_service", {}),
        "subdivision": data.get("selected_subdivision", {}),
        "execution_date": data.get("execution_date").strftime('%d.%m.%Y') if data.get("execution_date") else None,
        "form_data": data.get("form_data", {}),
        "uploaded_files": files_with_names,
        "user_id": callback.from_user.id,
        "username": callback.from_user.username
    }
    
    # Логируем JSON
    logger.info(f"Marketing request data: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    
    try:
        # Отправляем заявку в API
        response = await ItiliumBaseApi.create_marketing_request(
            telegram_id=callback.from_user.id,
            service=data.get("selected_service", {}).get("КомпонентаУслуги", ""),
            subdivision=data.get("selected_subdivision", ""),
            execution_date=data.get("execution_date").strftime('%Y.%m.%d') if data.get("execution_date") else "",
            form_data=data.get("form_data", {}),
            files=files_with_names
        )
        
        logger.info(f"API Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            # Удаляем сообщение с загрузкой и отправляем новое сообщение об успехе
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer("✅ Заявка успешно создана!")
        else:
            await callback.message.edit_text(
                "❌ Не удалось создать заявку. Проблемы на стороне Итилиума. Обратитесь к администратору."
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating marketing request: {e}")
        try:
            await callback.message.edit_text(
                "❌ Не удалось создать заявку. Проблемы на стороне Итилиума. Обратитесь к администратору."
            )
        finally:
            await state.clear()


@new_user_router.callback_query(F.data == "back_to_preview")
async def back_to_preview_callback(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к предварительному просмотру"""
    await callback.answer()
    await show_preview(callback.message, state)


@new_user_router.message(MarketingRequest.CONFIRM_REQUEST, F.text == "Отмена")
async def cancel_final_request(message: types.Message, state: FSMContext):
    """Отмена финального создания заявки"""
    await message.answer("Создание заявки отменено.")
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
