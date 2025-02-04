import json
import logging
import pathlib
from pathlib import Path

import httpx
from aiogram import types, Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.itilium_api import ItiliumBaseApi
from bot_enums.user_enums import UserButtonText
from filters.chat_types import ChatTypeFilter
from fsm.user_fsm import CreateNewIssue, CreateComment, ListNames
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
        "shortDescription": Helpers.prepare_short_description_for_sc(message.text),
    })

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
        reply_markup=get_keyboard(
            str(UserButtonText.CANCEL),
            str(UserButtonText.SEND_COMMENT)
        )
    )
    await state.set_state(CreateComment.comment)
    await state.update_data(sc_id=callback.data[6:])


@new_user_router.message(StateFilter(CreateComment.files))
@new_user_router.message(F.text)
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
        names: list = data.get("files", [])

        logger.debug(f"files: {names}")

        if names is None:
            await state.update_data(names=[])

        # names.append(file_path)
        names.append({
            "filename": file_path.split("/")[-1],  # file_13.jpg
            "file": file_path  # photos/file_13.jpg
        })

        await message.answer("Файл подготовлен к отправке")
        return

    await state.update_data(comment=message.text)
    await message.answer("Комментарий подготовлен к отправке")


@new_user_router.message(CreateComment.comment, F.text.casefold() == str(UserButtonText.SEND_COMMENT))
async def set_comment_for_sc(
        message: types.Message,
        state: FSMContext
):
@new_user_router.message(CreateComment.comment, F.text)
async def set_comment_for_sc(
        message: types.Message,
        state: FSMContext
):
    data = await state.get_data()

    logger.debug(f"comment: {message.text}")
    logger.debug(f"{message.from_user.id} | {data["sc_id"]}")

    response: Response = await ItiliumBaseApi.add_comment_to_sc(
        telegram_user_id=message.from_user.id,
        comment=message.text,
        sc_number=data["sc_id"]
    )

    await state.clear()
    await message.answer(
        "Комментарий добавлен",
        reply_markup=types.ReplyKeyboardRemove()
    )


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


@new_user_router.callback_query()
async def btn_all_callback(callback: types.CallbackQuery):
    """
    Обработчик ловит любые Callback
    """
    a = callback.data
    # show_sc$0000023773 при нажатии на кнопку "Открыть заявку"
    # reply$0000023773 при нажатии на кнопку "Добавить комментарий"
    logger.debug(f"{callback.from_user.id} | {callback.data}")
    await callback.answer()


# @new_user_router.message(F.photo)
# async def magic_filter_photo(
#         message: types.Message,
#         bot: Bot,
#         state: FSMContext
# ):
#     current_state = await state.get_state()
#     logger.debug(f"state {current_state}")
#
#     state_data = await state.get_data()
#     file_id = message.photo[-1].file_id
#     file_unique_id = message.photo[-1].file_unique_id
#
#     file = await bot.get_file(file_id)
#     file_path = file.file_path
#
#     logger.debug(f"file_id | {file_id}")
#     logger.debug(f"file_unique_id | {file_unique_id}")
#     logger.debug(f"file | {file}")
#     logger.debug(f"file_path | {file_path}")
#
#     # Save file to disc
#     # path_to_save = pathlib.Path(__file__).parent.resolve().parent / "files/photos" / file_path.split("/")[-1]
#     # await bot.download_file(file_path, path_to_save)
#     # await bot.download_file(file_path, file_path.split("/")[-1])
#
#     # (Photo) ('photos/file_0.jpg') https://api.telegram.org/bot<bot_token>/getFile?file_id=the_file_id
#     await message.answer("photo")


# @new_user_router.message(F.document)
# async def magic_filter(
#         message: types.Message,
#         bot: Bot
# ):
#     file_id = message.document.file_id
#     file_unique_id = message.document.file_unique_id
#
#     file = await bot.get_file(file_id)
#     file_path = file.file_path
#
#     logger.debug(f"file_id | {file_id}")
#     logger.debug(f"file_unique_id | {file_unique_id}")
#     logger.debug(f"file | {file}")
#     logger.debug(f"file_path | {file_path}")
#
#     path_to_save = pathlib.Path(__file__).parent.resolve().parent / "files/documents" / file_path.split("/")[-1]
#     await bot.download_file(file_path, path_to_save)
#     # await bot.download_file(file_path, file_path.split("/")[-1])
#
#     await message.answer("file")


# @new_user_router.message(F.video)
# async def magic_filter(
#         message: types.Message,
#         bot: Bot
# ):
#     file_id = message.video.file_id
#     file_unique_id = message.video.file_unique_id
#
#     file = await bot.get_file(file_id)
#     file_path = file.file_path
#
#     logger.debug(f"file_id | {file_id}")
#     logger.debug(f"file_unique_id | {file_unique_id}")
#     logger.debug(f"file | {file}")
#     logger.debug(f"file_path | {file_path}")
#
#     await message.answer("video")


# @new_user_router.message(F.voice)
# async def magic_filter(
#         message: types.Message,
#         bot: Bot
# ):
#     file_id = message.voice.file_id
#     file_unique_id = message.voice.file_unique_id
#
#     file = await bot.get_file(file_id)
#     file_path = file.file_path
#
#     logger.debug(f"file_id | {file_id}")
#     logger.debug(f"file_unique_id | {file_unique_id}")
#     logger.debug(f"file | {file}")
#     logger.debug(f"file_path | {file_path}")
#
#     await message.answer("voice")


# START STATE
# @new_user_router.message(StateFilter(None), F.text)
# async def test_filter(
#         message: types.Message,
#         state: FSMContext
# ):
#     await state.set_state(ListNames.files)
#     await state.update_data(files=[])
#     await state.set_state(ListNames.comment)
#     await message.answer("FSM start")


# @new_user_router.message(StateFilter(ListNames.files))
# @new_user_router.message(F.text)
# @new_user_router.message(F.photo)
# @new_user_router.message(F.video)
# @new_user_router.message(F.voice)
# @new_user_router.message(F.document)
# async def test_filter(
#         message: types.Message,
#         state: FSMContext,
#         bot: Bot
# ):
#     data = await state.get_data()
#
#     if (
#             message.photo or
#             message.video or
#             message.voice or
#             message.document
#     ) is not None:
#         file_path = await Helpers.get_file_info(message, bot)
#         names: list = data.get("files", [])
#
#         logger.debug(f"files: {names}")
#
#         if names is None:
#             await state.update_data(names=[])
#
#         # names.append(file_path)
#         names.append({
#             "filename": file_path.split("/")[-1],  # file_13.jpg
#             "file": file_path  # photos/file_13.jpg
#         })
#
#         await message.answer("Файл подготовлен к отправке")
#         return
#
#     await state.update_data(comment=message.text)
#     await message.answer("Комментарий подготовлен к отправке")

# END STATE

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
    #         # response = await client.request(
    #         #     headers={
    #         #         'Content-Type': 'multipart/form-data',
    #         #     },
    #         #     method="POST",
    #         #     # url="http://telegrambot_api_nginx/api/test",
    #         #     url="http://telegrambot_api_nginx/api/test",
    #         #     data={
    #         #         "description": "lorem ipsum dollar sit amet",
    #         #         "files": json_data
    #         #     },
    #         #     timeout=30.0
    #         # )
    #         #
    #         # logger.debug(f"status {response.status_code} | {response.text}")
    # except Exception as e:
    #     logger.exception(e)
    await message.answer(text="Я не понимаю Вашей команды (((")
