from datetime import date
from aiogram import F
from babel.dates import get_day_names, get_month_names
from aiogram_dialog import ChatEvent, DialogManager
from aiogram_dialog.widgets.kbd import (
    Calendar,
    CalendarScope,
    ManagedCalendar,
    SwitchTo,
)
from aiogram_dialog.widgets.kbd.calendar_kbd import (
    DATE_TEXT,
    TODAY_TEXT,
    CalendarDaysView,
    CalendarMonthView,
    CalendarScopeView,
    CalendarYearsView,
)
from aiogram_dialog.widgets.text import Const, Format, Text

from .calendar_states import CalendarDialog


class WeekDay(Text):
    """Кастомный виджет для отображения дней недели на русском языке"""
    
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        # Используем русскую локаль
        locale = "ru"
        return get_day_names(
            width="short", context="stand-alone", locale=locale,
        )[selected_date.weekday()].title()


class MarkedDay(Text):
    """Виджет для отображения отмеченных дней"""
    
    def __init__(self, mark: str, other: Text):
        super().__init__()
        self.mark = mark
        self.other = other

    async def _render_text(self, data, manager: DialogManager) -> str:
        current_date: date = data["date"]
        serial_date = current_date.isoformat()
        selected = manager.dialog_data.get("selected_dates", [])
        if serial_date in selected:
            return self.mark
        return await self.other.render_text(data, manager)


class Month(Text):
    """Кастомный виджет для отображения месяцев на русском языке"""
    
    async def _render_text(self, data, manager: DialogManager) -> str:
        selected_date: date = data["date"]
        # Используем русскую локаль
        locale = "ru"
        return get_month_names(
            "wide", context="stand-alone", locale=locale,
        )[selected_date.month].title()


class RussianCalendar(Calendar):
    """Кастомный календарь с русской локализацией"""
    
    def _init_views(self) -> dict[CalendarScope, CalendarScopeView]:
        return {
            CalendarScope.DAYS: CalendarDaysView(
                self._item_callback_data,
                date_text=MarkedDay("🔴", DATE_TEXT),
                today_text=MarkedDay("⭕", TODAY_TEXT),
                header_text="~~~~~ " + Month() + " ~~~~~",
                weekday_text=WeekDay(),
                next_month_text=Month() + " ▶",
                prev_month_text="◀ " + Month(),
            ),
            CalendarScope.MONTHS: CalendarMonthView(
                self._item_callback_data,
                month_text=Month(),
                header_text="~~~~~ " + Format("{date:%Y}") + " ~~~~~",
                this_month_text="✳" + Month() + "✳",
            ),
            CalendarScope.YEARS: CalendarYearsView(
                self._item_callback_data,
            ),
        }


async def on_date_clicked(
    callback: ChatEvent,
    widget: ManagedCalendar,
    manager: DialogManager,
    selected_date: date, /,
):
    """Обработчик клика по дате"""
    await callback.answer(f"Выбрана дата: {selected_date.strftime('%d.%m.%Y')}")
    # Закрываем диалог и передаем дату
    await manager.done({"selected_date": selected_date})


async def on_date_selected(
    callback: ChatEvent,
    widget: ManagedCalendar,
    manager: DialogManager,
    clicked_date: date, /,
):
    """Обработчик выбора даты с возможностью множественного выбора"""
    selected = manager.dialog_data.setdefault("selected_dates", [])
    serial_date = clicked_date.isoformat()
    if serial_date in selected:
        selected.remove(serial_date)
        await callback.answer(f"Дата {clicked_date.strftime('%d.%m.%Y')} удалена из выбора")
    else:
        selected.append(serial_date)
        await callback.answer(f"Дата {clicked_date.strftime('%d.%m.%Y')} добавлена в выбор")


async def selection_getter(dialog_manager, **_):
    """Геттер для отображения выбранных дат"""
    selected = dialog_manager.dialog_data.get("selected_dates", [])
    if selected:
        formatted_dates = [date.fromisoformat(d).strftime('%d.%m.%Y') for d in sorted(selected)]
        return {
            "selected": ", ".join(formatted_dates),
        }
    return {"selected": None}

