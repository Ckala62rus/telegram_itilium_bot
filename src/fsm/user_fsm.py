from aiogram.fsm.state import StatesGroup, State


class CreateNewIssue(StatesGroup):
    description = State()

    texts = {
        'AddProduct:description': 'Введите описание обращения:',
        'AddProduct:price': 'Введите стоимость заново:',
        'AddProduct:image': 'Этот стейт последний, поэтому...',
    }


class CreateComment(StatesGroup):
    comment = State()
