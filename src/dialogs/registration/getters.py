from typing import Any

from aiogram.types import User
from aiogram_dialog import DialogManager

from utils.message_templates import MessageTemplates


async def registration_getter(
    dialog_manager: DialogManager,
    **kwargs: Any,
) -> dict[str, Any]:
    event_user: User | None = getattr(dialog_manager.event, "from_user", None)
    telegram_id = str(event_user.id) if event_user else ""
    username = event_user.username if event_user else ""

    dialog_data = dialog_manager.dialog_data
    dialog_data.setdefault("telegram_input", telegram_id)

    return {
        "telegram_id": telegram_id,
        "username": username,
        "telegram_input": dialog_data.get("telegram_input", telegram_id),
        "fio": dialog_data.get("fio", ""),
        "organization": dialog_data.get("organization", ""),
        "subdivision": dialog_data.get("subdivision", ""),
        "position": dialog_data.get("position", ""),
        "reg_required": MessageTemplates.REGISTRATION_REQUIRED,
    }

