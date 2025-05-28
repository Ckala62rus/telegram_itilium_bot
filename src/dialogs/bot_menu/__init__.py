from aiogram_dialog import Dialog

from dialogs.bot_menu import windows


def bot_menu_dialogs():
    return [
        Dialog(
           windows.categories_window(),
            windows.product_window(),
        ),
        Dialog(
            windows.comment_for_change_sc_status(),
            windows.set_date_for_sc(),
            windows.confirm_change_state_sc(),
            windows.confirm_change_state_sc_without_date(),
        ),
    ]
