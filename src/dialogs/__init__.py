from aiogram import Dispatcher
from aiogram_dialog import setup_dialogs

from . import bot_menu


def custom_setup_dialogs(dp: Dispatcher):

    for dialog in bot_menu.bot_menu_dialogs():
        dp.include_router(dialog)

    setup_dialogs(dp)
