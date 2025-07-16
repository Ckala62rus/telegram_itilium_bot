from aiogram import types, Router, Bot, F
import logging

from filters.chat_types import ChatTypeFilter
from kbds.inline import get_callback_btns

user_group_router = Router()
user_group_router.message.filter(ChatTypeFilter(['group', 'supergroup']))

logger = logging.getLogger(__name__)


@user_group_router.message(F.text == 'www')
async def magic_filter_for_groups(
    message: types.Message,
):
    chai_id = message.chat.id
    text = message.text
    await message.answer(
        text=f"Вы написали {text} | chat_id {chai_id}",
        reply_markup=get_callback_btns(
            btns={"Тестовая кнопка": "test_button"},
        )
    )


@user_group_router.callback_query(F.data.startswith('test_button'))
async def magic_filter_for_groups(
    callback: types.CallbackQuery,
):
    await callback.answer("")
    await callback.message.answer(f"chat_id {callback.data} | test button pushed")
