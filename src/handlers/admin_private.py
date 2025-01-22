import logging

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession

from bot_enums.admin_enums import AdminEnums
from database.orm_query_user import get_user_by_phone_number, \
    set_admin_for_user
from filters.chat_types import ChatTypeFilter, IsAdminFromDatabase
from kbds.reply import get_keyboard


logger = logging.getLogger(__name__)
admin_router = Router()
admin_router.message.filter(ChatTypeFilter(['private']), IsAdminFromDatabase())

ADMIN_KB = get_keyboard(
    str(AdminEnums.ASSIGN_ADMIN),
    placeholder="Выберите действие",
    sizes=(2, 1, 1)
)

CANCEL_BT = get_keyboard(
    str(AdminEnums.CANCEL),
)


@admin_router.message(Command("admin"))
async def admin_panel(message: types.Message):
    await message.answer("Что хотите сделать?", reply_markup=ADMIN_KB)


class AddAdmin(StatesGroup):
    phone = State()
    confirm = State()

    texts = {
        'AddProduct:phone': 'Введите телефон заново для поиска пользователя:',
    }


@admin_router.message(StateFilter(None), F.text == str(AdminEnums.ASSIGN_ADMIN),)
async def find_user_for_set_admin(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите номер телефон для поиска ( пример: +78005553535 )",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AddAdmin.phone)


@admin_router.message(AddAdmin.phone, F.text)
async def set_phone_for_set_admin(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    await state.update_data(phone=message.text)
    user = await get_user_by_phone_number(db_session, message.text)

    text = """
        *** Информация о пользователе ***
    ID: {id}
    Username: {username}
    Telegram ID: {telegram_id}
    Phone number: {phone}
    Created at: {created_at}
    """.format(
        id=user.id,
        username=user.username,
        telegram_id=user.telegram_id,
        phone=user.phone_number,
        created_at=user.created_at,
    )

    await message.answer(text=text)
    await message.answer(
        text="Предоставить админские права?",
        reply_markup=get_keyboard(
            str(AdminEnums.YES),
            str(AdminEnums.CANCEL),
        )
    )
    await state.set_state(AddAdmin.confirm)


@admin_router.message(AddAdmin.confirm, F.text)
async def confirm_admin_create(
        message: types.Message,
        state: FSMContext,
        db_session: AsyncSession
):
    # if message.text == str(AdminEnums.YES):
    await state.update_data(confirm=message.text)
    data = await state.get_data()
    await message.answer("Права администратора добавлены")
    await set_admin_for_user(db_session, data["phone"], True)
    await state.clear()


# @admin_router.message(F.text)
# async def start_command(message: types.Message):
#     await message.answer(text="Это магический фильтр из админской ветки")

# todo Сделать функционал по добавлению прав пользователя,
# todo Сделать функционал для возможности бана и разблокировки пользователя.
# todo Сделать функционал по поиску пользователя по номеру телефона
