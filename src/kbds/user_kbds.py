from kbds.inline import get_callback_btns

USER_MENU_KEYBOARD = get_callback_btns(
    btns={
        "Заявки в моей ответственности 💼":"responsibility_scs_client",
        "Мои заявки ✒":"scs_client",
        "Поиск заявки по номеру 🔎":"scs_search",
        # "Вернуться в начало ↩":"to_initial_state",
        "Создать заявку 🎈":"crate_new_issue",
    },
    size=(1,2,1),
)
