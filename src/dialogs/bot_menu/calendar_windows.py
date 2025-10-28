from aiogram import F
from aiogram_dialog import Window
from aiogram_dialog.widgets.kbd import SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from .calendar_states import CalendarDialog
from .calendar_widgets import (
    RussianCalendar,
    on_date_clicked,
    on_date_selected,
    selection_getter
)


def calendar_main_window():
    """Главное окно календаря"""
    return Window(
        Const("📅 Выберите тип календаря:"),
        SwitchTo(
            Const("📆 Обычный календарь"),
            id="default",
            state=CalendarDialog.DEFAULT,
        ),
        SwitchTo(
            Const("📋 Календарь с выбором дат"),
            id="custom",
            state=CalendarDialog.CUSTOM,
        ),
        SwitchTo(
            Const("🔙 Назад в главное меню"),
            id="back_to_main",
            state=CalendarDialog.MAIN,
        ),
        state=CalendarDialog.MAIN,
        getter=selection_getter,
    )


def calendar_default_window():
    """Окно обычного календаря"""
    return Window(
        Const("📆 Обычный календарь\n\nВыберите дату:"),
        RussianCalendar(
            id="cal",
            on_click=on_date_clicked,
        ),
        SwitchTo(
            Const("🔙 Назад к выбору"),
            id="back_to_calendar_main",
            state=CalendarDialog.MAIN,
        ),
        state=CalendarDialog.DEFAULT,
    )


def calendar_custom_window():
    """Окно календаря с множественным выбором"""
    return Window(
        Const("📋 Календарь с выбором дат\n\nВыберите нужные даты:"),
        Format("\n✅ Выбранные даты: {selected}", when=F["selected"]),
        Format("\n❌ Даты не выбраны", when=~F["selected"]),
        RussianCalendar(
            id="cal",
            on_click=on_date_selected,
        ),
        SwitchTo(
            Const("🔙 Назад к выбору"),
            id="back_to_calendar_main",
            state=CalendarDialog.MAIN,
        ),
        getter=selection_getter,
        state=CalendarDialog.CUSTOM,
    )





