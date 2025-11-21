from aiogram.fsm.state import State, StatesGroup


class RegistrationDialog(StatesGroup):
    enter_telegram = State()
    enter_fio = State()
    enter_organization = State()
    enter_subdivision = State()
    enter_position = State()
    confirm = State()

