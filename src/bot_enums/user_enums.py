from enum import StrEnum


class FindPartyTypes(StrEnum):
    LOOKING_FOR = "искать партию"
    SIMPLE = "простой поиск",
    WITH_COLOR = "искать партию с цветом",
    WITH_FIO = "искать с фио",
    CANCEL = "отмена",
    STEP_BACK = "шаг назад"


class FindPartyText(StrEnum):
    CHOOSE_YEAR = "Выберете год или введите две цифры нужного"
    SEND_YOUR_PHONE = "Отправьте свой номер телефона для регистрации"
    ACTIONS_CANCELED = "Действия отменены"
    PLEASE_ENTER_PART_NUMBER = "Введите номер партии для поиска"
    ADDITION_INFORMATION = ("Если нужна дополнительная информация о партии, "
                            "выберете соответствующую кнопку "
                            "(запрос займет немного больше времени)?")
    LOOKING_PARTY = "Поиск партии..."
    SUCCESS_PHONE_ADD = "Телефон успешно сохранен"
