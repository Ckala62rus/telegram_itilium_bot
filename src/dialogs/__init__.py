from aiogram import Dispatcher
from aiogram_dialog import setup_dialogs

from . import bot_menu, registration


def custom_setup_dialogs(dp: Dispatcher):

    for dialog in bot_menu.bot_menu_dialogs():
        dp.include_router(dialog)
    
    for dialog in registration.registration_dialogs():
        dp.include_router(dialog)

    setup_dialogs(dp)
