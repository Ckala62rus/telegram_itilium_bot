from aiogram_dialog import Dialog

from dialogs.registration import windows


def registration_dialogs() -> list[Dialog]:
    return [
        Dialog(
            windows.request_telegram(),
            windows.request_fio(),
            windows.request_organization(),
            windows.request_subdivision(),
            windows.request_position(),
            windows.confirm_registration(),
        )
    ]

