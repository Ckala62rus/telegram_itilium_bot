from aiogram.fsm.state import StatesGroup, State
from utils.logger_project import setup_logger


__all__ = [
    'ConfirmSc',
    'LoadPagination',
    'CreateNewIssue',
    'CreateComment',
    'SearchSC',
]


logger = setup_logger(__name__)


class CreateNewIssue(StatesGroup):
    description = State()
    files = State()
    # ready_to_send = State()

    texts = {
        'AddProduct:description': 'Введите описание обращения:',
        'AddProduct:price': 'Введите стоимость заново:',
        'AddProduct:image': 'Этот стейт последний, поэтому...',
    }


class CreateComment(StatesGroup):
    comment = State()
    files = State()
    sc_id = State()


class SearchSC(StatesGroup):
    sc_number = State()
    preview_message = State()


class LoadPagination(StatesGroup):
    load = State()


class LoadPaginationResponsible(StatesGroup):
    load = State()


class ConfirmSc(StatesGroup):
    grade = State()
    sc_number = State()
    comment = State()
    message_with_choice_grade = State()
    messages_ids = State()
