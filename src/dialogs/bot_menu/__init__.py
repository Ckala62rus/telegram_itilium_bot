from aiogram_dialog import Dialog

from dialogs.bot_menu import windows
from dialogs.bot_menu.calendar_windows import (
    calendar_main_window,
    calendar_default_window,
    calendar_custom_window,
)


def bot_menu_dialogs():
    return [
        Dialog(
            windows.comment_for_change_sc_status(),
            windows.set_date_for_sc(),
            windows.confirm_change_state_sc(),
            windows.confirm_change_state_sc_without_date(),
        ),
        Dialog(
            windows.set_date_for_marketing(),
        ),
        Dialog(
            calendar_main_window(),
            calendar_default_window(),
            calendar_custom_window(),
        ),
    ]
