from kbds.inline import get_callback_btns

USER_MENU_KEYBOARD = get_callback_btns(
    btns={
        "Мои заявки ✒":"scs_client",
        "Поиск заявки по номеру 🔎":"scs_search",
        "Вернуться в начало ↩":"to_initial_state",
    },
)
