import logging
from typing import Any

import httpx
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button

from api.itilium_api import ItiliumBaseApi
from dialogs.registration.states import RegistrationDialog
from utils.message_templates import MessageTemplates

logger = logging.getLogger(__name__)


async def _save_text_value(
    message: Message,
    manager: DialogManager,
    key: str,
    value: Any,
    next_state: State,
) -> None:
    cleaned_value = value.strip() if isinstance(value, str) else value

    if not cleaned_value:
        await message.answer("Поле не может быть пустым. Повторите ввод.")
        return

    manager.dialog_data[key] = cleaned_value
    await manager.switch_to(next_state)


async def save_telegram(
    message: Message,
    widget: Any,
    manager: DialogManager,
    value: str,
) -> None:
    cleaned_value = value.strip()
    if not cleaned_value:
        await message.answer("Введите значение. Можно использовать предложенный Telegram ID.")
        return

    manager.dialog_data["telegram_input"] = cleaned_value
    await manager.switch_to(RegistrationDialog.enter_fio)


async def save_fio(
    message: Message,
    widget: Any,
    manager: DialogManager,
    value: str,
) -> None:
    await _save_text_value(
        message=message,
        manager=manager,
        key="fio",
        value=value,
        next_state=RegistrationDialog.enter_organization,
    )


async def save_organization(
    message: Message,
    widget: Any,
    manager: DialogManager,
    value: str,
) -> None:
    await _save_text_value(
        message=message,
        manager=manager,
        key="organization",
        value=value,
        next_state=RegistrationDialog.enter_subdivision,
    )


async def save_subdivision(
    message: Message,
    widget: Any,
    manager: DialogManager,
    value: str,
) -> None:
    await _save_text_value(
        message=message,
        manager=manager,
        key="subdivision",
        value=value,
        next_state=RegistrationDialog.enter_position,
    )


async def save_position(
    message: Message,
    widget: Any,
    manager: DialogManager,
    value: str,
) -> None:
    await _save_text_value(
        message=message,
        manager=manager,
        key="position",
        value=value,
        next_state=RegistrationDialog.confirm,
    )


async def use_detected_telegram(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    await callback.answer()
    manager.dialog_data["telegram_input"] = str(callback.from_user.id)
    await manager.switch_to(RegistrationDialog.enter_fio)


async def submit_registration(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    await callback.answer()
    dialog_data = manager.dialog_data

    payload = {
        "telegram": dialog_data.get("telegram_input") or str(callback.from_user.id),
        "FIO": dialog_data.get("fio", ""),
        "Organization": dialog_data.get("organization", ""),
        "Subdivision": dialog_data.get("subdivision", ""),
        "NamePosition": dialog_data.get("position", ""),
    }

    logger.info("Собранные данные для регистрации: %s", payload)

    target_message = callback.message
    if target_message is None:
        target_message = await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Отправляю заявку на регистрацию..."
        )
    else:
        target_message = await target_message.reply("Отправляю заявку на регистрацию...")

    try:
        response = await ItiliumBaseApi.create_registration_request(payload)
        if response.status_code in (httpx.codes.OK, httpx.codes.CREATED):
            await target_message.edit_text(MessageTemplates.REGISTRATION_SUCCESS)
        else:
            logger.error(
                "Ошибка регистрации. Код: %s | Тело: %s",
                response.status_code,
                response.text
            )
            await target_message.edit_text(MessageTemplates.REGISTRATION_FAILED)
    except Exception as error:
        logger.exception("Ошибка при отправке регистрации: %s", error)
        await target_message.edit_text(MessageTemplates.REGISTRATION_FAILED)
    finally:
        await manager.done()


async def cancel_registration(
    callback: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    await callback.answer()
    await manager.done()

    if callback.message:
        await callback.message.answer(MessageTemplates.REGISTRATION_CANCELED)
    else:
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=MessageTemplates.REGISTRATION_CANCELED
        )

