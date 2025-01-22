from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_callback_btns(
        *,
        btns: dict[str, str | object],
        size: tuple[int] = (2,),
        btns_last: dict[str, str] = None,
        size_last: tuple[int] = (1,)
):
    keyboard = InlineKeyboardBuilder()

    for text, data in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, callback_data=data))

    if btns_last is not None and len(btns_last) > 0:
        for key, value in btns_last.items():
            keyboard.add(InlineKeyboardButton(text=key, callback_data=value))

    return keyboard.adjust(*size).as_markup()


def get_url_btns(
        *,
        btns: dict[str, str],
        size: tuple[int] = (2,)
):
    keyboard = InlineKeyboardBuilder()

    for text, url in btns.items():
        keyboard.add(InlineKeyboardButton(text=text, url=url))

    return keyboard.adjust(*size).as_markup()


def get_inline_mix_btns(
        *,
        btns: dict[str, str],
        size: tuple[int] = (2,)
):
    keyboard = InlineKeyboardBuilder()

    for text, value in btns.items():
        if '://' in value:
            keyboard.add(InlineKeyboardButton(text=text, url=value))
        else:
            keyboard.add(InlineKeyboardButton(text=text, callback_data=value))

    return keyboard.adjust(*size).as_markup()
