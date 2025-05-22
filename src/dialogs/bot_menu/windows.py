from aiogram_dialog import Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Cancel, Back, Button, Calendar, Group, CalendarScope
from aiogram_dialog.widgets.text import Const

from dialogs.bot_menu import keyboards, states, getters
from dialogs.bot_menu import selected
from dialogs.bot_menu.states import ChangeScStatus


def categories_window():
    return Window(
        Const("Choose category that you want"),
        keyboards.paginated_categories(selected.on_chosen_category),
        Cancel(Const("Exit")),
        state=states.BotMenu.select_categories,
        getter=getters.get_categories,
    )

def product_window():
    return Window(
        Const("Choose product that you want"),
        Back(Const("<< Select another category")),
        Cancel(Const("Exit")),
        state=states.BotMenu.select_products,
        getter=getters.get_categories,
    )

def comment_for_change_sc_status():
    return Window(
        Const("Для статуса 'Отложено' комментарий обязателен! Введите комментарий"),
        TextInput(
            id="comment_for_sc",
            on_success=selected.confirm_comment,
        ),
        Cancel(Const("Отмена")),
        state=ChangeScStatus.enter_comment
    )


def set_date_for_sc():
    return Window(
        Const("Выберите дату, до которой нужно отложить задачу."),
        Back(Const("Назад ко вводу комментария")),
        Cancel(Const("Отмена")),
        Calendar(id='calendar', on_click=selected.on_date_selected),
        state = ChangeScStatus.enter_date
    )

def confirm_change_state_sc():
    return Window(
        Const("Подтвердите смену статуса."),
        Back(Const("Назад к выбору даты ↩")),
        Group(
            Cancel(Const("Отмена ❌")),
            Button(
                text=Const("Подтвердить ✅"),
                on_click=selected.confirm_change_state_sc_on_new,
                id="change_state_sc"
            ),
            width=2
        ),
        state=ChangeScStatus.confirm
    )
