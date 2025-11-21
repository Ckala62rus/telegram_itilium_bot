import logging
from typing import Any, Awaitable, Callable

import httpx
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError

from api.itilium_api import ItiliumBaseApi
from dialogs.registration.states import RegistrationDialog
from utils.message_templates import MessageTemplates

logger = logging.getLogger(__name__)


class UserAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message = self._extract_message(event)
        if message is None:
            return await handler(event, data)

        if getattr(message.chat, "type", None) != "private":
            return await handler(event, data)

        telegram_id = self._extract_telegram_id(event)
        if telegram_id is None:
            return await handler(event, data)

        dialog_manager: DialogManager | None = data.get("dialog_manager")
        if dialog_manager and self._is_registration_dialog(dialog_manager):
            return await handler(event, data)

        try:
            response = await ItiliumBaseApi.find_employee_by_attribute(telegram_id)
        except Exception as error:
            logger.error("Ошибка проверки пользователя %s: %s", telegram_id, error)
            await self._reply(message, data, MessageTemplates.ITILIUM_ERROR)
            return

        status = response.status_code
        if status == httpx.codes.OK:
            data["itilium_employee_response"] = response
            return await handler(event, data)

        if status == httpx.codes.UNAUTHORIZED:
            logger.info("Пользователь %s не найден в Итилиуме. Запускаем регистрацию.", telegram_id)
            await self._answer_callback(event)
            if dialog_manager:
                try:
                    await dialog_manager.start(
                        state=RegistrationDialog.enter_telegram,
                        data={"telegram": str(telegram_id)},
                        mode=StartMode.RESET_STACK,
                    )
                except Exception as start_error:
                    logger.exception("Не удалось запустить диалог регистрации: %s", start_error)
                    await self._reply(message, data, MessageTemplates.REGISTRATION_REQUIRED)
            else:
                await self._reply(message, data, MessageTemplates.REGISTRATION_REQUIRED)
            return

        if status == httpx.codes.FORBIDDEN:
            logger.info("Пользователь %s ожидает подтверждения регистрации.", telegram_id)
            await self._answer_callback(event)
            await self._reply(message, data, MessageTemplates.REGISTRATION_PENDING)
            return

        logger.error(
            "Неожиданный ответ find_employee для %s. Код: %s | Тело: %s",
            telegram_id,
            response.status_code,
            response.text,
        )
        await self._reply(message, data, MessageTemplates.ITILIUM_ERROR)
        return

    @staticmethod
    async def _answer_callback(event: TelegramObject) -> None:
        callback = None
        if isinstance(event, CallbackQuery):
            callback = event
        elif isinstance(event, Update):
            callback = event.callback_query

        if callback:
            try:
                await callback.answer()
            except Exception:
                pass

    @staticmethod
    def _extract_telegram_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                return event.message.from_user.id
            if event.edited_message and event.edited_message.from_user:
                return event.edited_message.from_user.id
            if event.callback_query and event.callback_query.from_user:
                return event.callback_query.from_user.id
        return None

    @staticmethod
    def _extract_message(event: TelegramObject) -> Message | None:
        if isinstance(event, Message):
            return event
        if isinstance(event, CallbackQuery):
            return event.message
        if isinstance(event, Update):
            if event.message:
                return event.message
            if event.edited_message:
                return event.edited_message
            if event.callback_query and event.callback_query.message:
                return event.callback_query.message
        return None

    @staticmethod
    async def _reply(message: Message | None, data: dict[str, Any], text: str) -> None:
        if message:
            await message.answer(text)
            return

        bot = data.get("bot")
        from_user = data.get("event_from_user")

        if bot and from_user:
            await bot.send_message(chat_id=from_user.id, text=text)

    @staticmethod
    def _is_registration_dialog(dialog_manager: DialogManager) -> bool:
        try:
            if not dialog_manager.has_context():
                return False
            context = dialog_manager.current_context()
            return context.state.group == RegistrationDialog
        except NoContextError:
            return False

