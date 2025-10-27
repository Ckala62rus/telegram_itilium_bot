from aiogram.fsm.state import StatesGroup, State


class CalendarDialog(StatesGroup):
    """Состояния для диалога с календарем"""
    MAIN = State()
    DEFAULT = State()
    CUSTOM = State()
    DATE_SELECTION = State()


