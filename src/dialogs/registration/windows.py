from aiogram_dialog import Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Group
from aiogram_dialog.widgets.text import Const, Format

from dialogs.registration import handlers
from dialogs.registration.getters import registration_getter
from dialogs.registration.states import RegistrationDialog


def _cancel_button(widget_id: str) -> Button:
    return Button(
        text=Const("Отмена ❌"),
        id=widget_id,
        on_click=handlers.cancel_registration,
    )


def request_telegram() -> Window:
    return Window(
        Format(
            "{reg_required}\n\n"
            "Я определил ваш Telegram ID: <b>{telegram_id}</b>.\n"
            "Если всё верно, нажмите кнопку ниже.\n"
            "При необходимости отправьте другое значение (например, @username или номер телефона)."
        ),
        TextInput(
            id="registration_telegram",
            on_success=handlers.save_telegram,
        ),
        Group(
            Button(
                text=Const("Использовать этот ID ✅"),
                id="registration_use_detected",
                on_click=handlers.use_detected_telegram,
            ),
            _cancel_button("registration_cancel_telegram"),
            width=1,
        ),
        state=RegistrationDialog.enter_telegram,
        getter=registration_getter,
    )


def request_fio() -> Window:
    return Window(
        Const("Введите ваше ФИО полностью:"),
        TextInput(
            id="registration_fio",
            on_success=handlers.save_fio,
        ),
        _cancel_button("registration_cancel_fio"),
        state=RegistrationDialog.enter_fio,
    )


def request_organization() -> Window:
    return Window(
        Const("Укажите название вашей организации:"),
        TextInput(
            id="registration_org",
            on_success=handlers.save_organization,
        ),
        _cancel_button("registration_cancel_org"),
        state=RegistrationDialog.enter_organization,
    )


def request_subdivision() -> Window:
    return Window(
        Const("Укажите подразделение сотрудника:"),
        TextInput(
            id="registration_subdivision",
            on_success=handlers.save_subdivision,
        ),
        _cancel_button("registration_cancel_subdivision"),
        state=RegistrationDialog.enter_subdivision,
    )


def request_position() -> Window:
    return Window(
        Const("Введите должность (NamePosition):"),
        TextInput(
            id="registration_position",
            on_success=handlers.save_position,
        ),
        _cancel_button("registration_cancel_position"),
        state=RegistrationDialog.enter_position,
    )


def confirm_registration() -> Window:
    return Window(
        Format(
            "Проверьте данные перед отправкой:\n\n"
            "• Telegram: {telegram_input}\n"
            "• ФИО: {fio}\n"
            "• Организация: {organization}\n"
            "• Подразделение: {subdivision}\n"
            "• Должность: {position}\n"
        ),
        Group(
            Button(
                text=Const("Отправить ✅"),
                id="registration_submit",
                on_click=handlers.submit_registration,
            ),
            _cancel_button("registration_cancel_finish"),
            width=2,
        ),
        state=RegistrationDialog.confirm,
        getter=registration_getter,
    )

