from datetime import date
from typing import Any

import httpx
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import DialogManager
from httpx import Response

from api.itilium_api import ItiliumBaseApi
from dialogs.bot_menu.states import BotMenu, ChangeScStatus


async def on_chosen_category(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str
):
    print("Fruit selected: ", item_id)
    ctx = manager.current_context()
    ctx.dialog_data.update(category_id=item_id)
    await manager.switch_to(BotMenu.select_products)


async def confirm_comment(
    message: Message,
    dialog_: Any,
    manager: DialogManager,
    comment : Any
):
    """
    Проверяем длинну комментария для TextInput виджета.
    Используется для логики добавления коментария для задачи при
    изменении статуса на 'Отложено'
    """
    if len(comment) <= 0:
        await message.answer("Был введен пустой комментарий")
        return

    if len(comment) < 5:
        await message.answer("Был введен короткий комментарий")
        return

    ctx = manager.current_context()
    ctx.dialog_data.update(comment=comment)

    await manager.switch_to(ChangeScStatus.enter_date)


async def on_date_selected(
    callback: CallbackQuery,
    widget,
    manager: DialogManager,
    selected_date: date,
):
    ctx = manager.current_context()
    ctx.dialog_data.update(new_date=str(selected_date))

    await callback.answer()
    await manager.switch_to(ChangeScStatus.confirm)


async def confirm_change_state_sc_on_new(
    callback: CallbackQuery,
    widget: Any,
    manager: DialogManager,
):
    data: dict = manager.start_data
    ctx = manager.current_context()

    comment = ctx.dialog_data.get('comment')
    new_date = ctx.dialog_data.get('new_date')
    sc_number = data['sc_number']
    new_state = data['new_state']

    await callback.answer()
    await callback.message.answer(
        f"""
        comment: {comment}
        new_date: {new_date}
        sc_number: {sc_number}
        new_state: {new_state}
        Данные отправлены!
        """
    )
    await manager.done()

    send_data_to_api = await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text="Делаю запрос. Подождите!"
    )

    result: Response = await ItiliumBaseApi.change_sc_state_with_comment(
        telegram_user_id=callback.from_user.id,
        sc_number=sc_number,
        state=new_state,
        comment=comment,
        date_inc=new_date
    )

    if result.status_code == httpx.codes.OK:
        await send_data_to_api.delete()
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text="Статус заявки был изменен успешно! ✔"
        )
    else:
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=f"""
            Что-то пошло не так... 💥
            Ошибка: {result.text}
            """
        )
