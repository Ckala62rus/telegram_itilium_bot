from aiogram.fsm.state import StatesGroup, State


class BotMenu(StatesGroup):
    select_categories = State()
    select_products = State()
    product_info = State()


class BuyProduct(StatesGroup):
    enter_amount = State()
    confirm = State()

class ChangeScStatus(StatesGroup):
    enter_comment = State()
    enter_date = State()
    confirm = State()
    confirm_without_date = State()
