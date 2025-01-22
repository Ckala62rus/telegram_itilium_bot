from enum import StrEnum


class AdminEnums(StrEnum):
    CANCEL = "отмена операции",
    YES = "да",
    ASSIGN_ADMIN = "назначить админа",
    UNSET_ASSIGN_ADMIN = "отобрать админские права",
    FIND_USER_BY_NUMBER = "найти пользователя по номеру",
    FIND_USER_BY_ID = "найти пользователя по ID",
    FIND_USER_BY_TELEGRAM_ID = "найти пользователя по ID Telegram",
    ADMIN_MENU = "админка",
    SET_BAN = "заблокировать пользователя",
    REMOVE_BAN = "разблокировать пользователя",
