import logging

from aiogram import types, Router, F
from aiogram.filters import CommandStart, Command
from sqlalchemy.ext.asyncio import AsyncSession

from bot_enums.user_enums import FindPartyText
from database.models.models import User
from database.orm_query_user import get_user_by_telegram_id, add_user, update_phone_user
from filters.chat_types import ChatTypeFilter
from kbds import reply

new_user_router = Router()
new_user_router.message.filter(ChatTypeFilter(['private']))

logger = logging.getLogger(__name__)


@new_user_router.message(CommandStart())
async def start_command(message: types.Message, db_session: AsyncSession):
    user: User = await get_user_by_telegram_id(db_session, message.from_user.id)

    logger.debug("Command start")
    logger.info(message.from_user.id)

    if user is not None:
        logger.debug(f"User with id {user.id}")
        if len(user.phone_number) > 0:
            logger.debug(user.phone_number)
            await message.answer(text="Вы уже есть в системе")
            return

    if user is None:
        logger.debug("User is not found in database")
        await add_user(db_session, {
            "username": message.from_user.username,
            "telegram_id": message.from_user.id,
        })

    await message.answer(
        text="Для того, что бы пользоваться ботом, "
             "вам необходимо поделиться номером телефона и "
             "сообщить администратору, для добавления прав",
        reply_markup=reply.phone_kb
    )

    logger.debug("End start")


@new_user_router.message(F.contact)
async def phone_number(message: types.Message, db_session: AsyncSession):
    phone = message.contact.phone_number
    await update_phone_user(
        phone=phone,
        session=db_session,
        telegram_id=message.from_user.id
    )
    logger.debug(f"Save user phone {message.contact.phone_number}")
    await message.answer(
        text=str(FindPartyText.SUCCESS_PHONE_ADD),
        reply_markup=types.ReplyKeyboardRemove()
    )


@new_user_router.message(Command('phone'))
async def phone_command(message: types.Message, db_session: AsyncSession):
    logger.debug(f"Send button phone for user {message.from_user.id}")
    await message.answer(
        text=str(FindPartyText.SEND_YOUR_PHONE),
        reply_markup=reply.phone_kb
    )
