from aiogram_dialog import Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Cancel, Back, Button, Calendar, Group, CalendarScope
from aiogram_dialog.widgets.text import Const
import logging

from dialogs.bot_menu import selected
from dialogs.bot_menu.states import ChangeScStatus

logger = logging.getLogger(__name__)

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

def confirm_change_state_sc_without_date():
    return Window(
        Const("Подтвердите смену статуса."),
        Group(
            Cancel(Const("Отмена ❌")),
            Button(
                text=Const("Подтвердить ✅"),
                on_click=selected.confirm_change_state_sc_on_new,
                id="change_state_sc"
            ),
            width=2
        ),
        state=ChangeScStatus.confirm_without_date
    )
