from aiogram.fsm.state import StatesGroup, State


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
