from string import punctuation

from aiogram import types, Router, Bot
from aiogram.filters import Command

from filters.chat_types import ChatTypeFilter

user_group_router = Router()
user_group_router.message.filter(ChatTypeFilter(['group', 'supergroup']))

restricted_words = {'чушпан', 'хуй'}


@user_group_router.message(Command("admin"))
async def get_admins(messages: types.Message, bot: Bot):
    chat_id = messages.chat.id
    admins_list = await bot.get_chat_administrators(chat_id)

    admins_list = [
        member.user.id
        for member in admins_list
        if member.status == "creator" or member.status == "administrator"
    ]

    bot.my_admins_list = admins_list
    if messages.from_user.id in admins_list:
        await messages.delete()


def clean_text(text: str):
    return text.translate(str.maketrans('', '', punctuation))


@user_group_router.message()
async def cleaner(message: types.Message):
    if restricted_words.intersection(message.text.lower().split()):
        await message.answer(f"{message.from_user.username}, соблюдай порядок в чате пёс!")
        await message.delete()
        # if you need ban person
        # await message.chat.ban(message.from_user.id)
