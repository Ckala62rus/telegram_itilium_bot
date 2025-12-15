import json
import logging
import re

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from io import StringIO
from html.parser import HTMLParser
from utils.logger_project import setup_logger

logger = setup_logger(__name__)


class MLStripper(HTMLParser):
    """
    Delete html tags from text
    """
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d: str) -> str:
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


class Helpers:

    def prepare_short_description_for_sc(sc_description: str):
        """
        Метод, подготавливающий тему заявки из введенного описания этой заявки. Если длина заявки более 30 символов,
        то тема формируется из первых 30 символов описания. При этом если последнее слово, взятое в тему заявки, будет
        разбито на две части, то все это слово отбрасывается. Если же длина описания заявки менее 30 символов, то
        тема заявки полностью скопирует описание заявки.
        :param sc_description: описание формируемой заявки
        :return: возвращает подготовленную тему создаваемой завки
        """
        if len(sc_description) > 30:
            words_list = sc_description.split(' ')
            short_description = ''
            for word in words_list:
                if len(short_description) + len(word) + 1 <= 31:
                    short_description = f'{short_description} {word}'
                else:
                    break
            return f'{short_description.lstrip()}...'
        else:
            return sc_description

    # Метод подготовки текста заявки. Принимает на вход:
    # param input_data - JSON-ответ с параметрами заявки
    # Функция возвращает заполненный ассоциативный массив (словарь) с данными отправляемого сообщения
    def prepare_sc(input_data: dict):
        # Создаем словарь с необходимыми атрибутами
        sc_attr = {
            "number": "<b>Заявка:</b> № ",
            "shortDescription": "<b>Тема:</b> ",
            "state": "<b>Статус:</b> ",
            "responsibleEmployee": "<b>Ответственный специалист:</b> ",
            "deadlineDate": "<b>Срок решения заявки:</b> ",
            "description": "<b>Описание:</b> ",
        }
        # Номер заявки
        sc_attr["number"] += str(input_data["number"])
        # Тема заявки
        if input_data["shortDescription"] is not None:
            sc_attr["shortDescription"] += input_data["shortDescription"]
        # Статус заявки
        sc_attr["state"] += input_data["state"]
        # Ответственный специалист
        if input_data["responsibleTeamTitle"] is not None:
            sc_attr["responsibleEmployee"] += input_data["responsibleTeamTitle"]
        # Срок решения заявки
        if input_data["deadlineDate"] is not None:
            sc_attr["deadlineDate"] += input_data["deadlineDate"]
        # Описание заявки
        sc_attr["description"] += re.sub(re.compile('<.*?>'), '', input_data["description"])
        # форимируем окончательно текст отправляемого сообщения
        output_data = ''
        for key in sc_attr:
            output_data += (str(sc_attr[key]) + '\n\r')
        return output_data

    @staticmethod
    async def get_file_info(message: Message, bot: Bot) -> str | None:
        """
        Метод олределяет тип файла (видео, фото, голос, видео или документ).
        Далее, получив file_id делает запрос к телеграму для получения пути.
        И возвращает путь.
        Например:
            voice/file_20.oga
            documents/file_21.pdf
            photos/file_19.jpg
        :return: путь до файла (photos/file_19.jpg). str
        """
        file_id = None
        file_unique_id = None

        if message.voice:
            file_id = message.voice.file_id
            file_unique_id = message.voice.file_unique_id
        if message.photo:
            file_id = message.photo[-1].file_id
            file_unique_id = message.photo[-1].file_unique_id
        if message.video:
            file_id = message.video.file_id
            file_unique_id = message.video.file_unique_id
        if message.document:
            file_id = message.document.file_id
            file_unique_id = message.document.file_unique_id

        file = await bot.get_file(file_id)
        file_path = file.file_path

        logger.debug(f"file_id | {file_id}")
        logger.debug(f"file_unique_id | {file_unique_id}")
        logger.debug(f"file | {file}")
        logger.debug(f"file_path | {file_path}")

        return file_path

    @staticmethod
    def _prepare_marketing_preview(description: str | None, limit: int = 64) -> str:
        """
        Возвращает усечённое описание для маркетинговых заявок.
        Длина возвращаемой строки не превышает limit и всегда
        включает троеточие, если произошла обрезка.
        """
        if not description:
            return ""

        cleaned = re.sub(re.compile('<.*?>'), '', description).strip()
        if not cleaned:
            return ""

        if len(cleaned) <= limit:
            return cleaned

        if limit <= 3:
            return "..."[:limit]

        return f"{cleaned[:limit - 3].rstrip()}..."

    @staticmethod
    def _deserialize_sc(entry: object) -> dict | None:
        """
        Приводит элемент из Redis/ответа API к словарю заявки.
        Поддерживаются dict, bytes и str (JSON).
        """
        if isinstance(entry, dict):
            return entry

        if isinstance(entry, (bytes, bytearray)):
            try:
                entry = entry.decode()
            except Exception:
                return None

        if isinstance(entry, str):
            try:
                entry = json.loads(entry)
            except json.JSONDecodeError:
                logger.warning("Не удалось распарсить данные заявки: %s", entry)
                return None

        if isinstance(entry, dict):
            return entry

        logger.warning("Неподдерживаемый формат заявки: %s", type(entry))
        return None

    @staticmethod
    async def get_paginated_kb_scs(scs: list, page: int = 0) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        start_offset = page * 10
        end_offset = start_offset + 10
        count_page = len(scs)

        for elem in scs[start_offset:end_offset]:
            sc = Helpers._deserialize_sc(elem)
            if not sc:
                continue
            button_text = f"({sc.get('number')}) {sc.get('shortDescription', '')}"

            if sc.get("marketing") and sc.get("description"):
                preview = Helpers._prepare_marketing_preview(sc.get("description"))
                if preview:
                    button_text = f"{button_text} — {preview}"

            builder.row(InlineKeyboardButton(
                text=button_text,
                callback_data=f"show_sc${sc.get('number')}"
            ))

        buttons_row = []

        if page > 0:
            buttons_row.append(InlineKeyboardButton(text="⬅️",callback_data=f"sc_page_{page - 1}",))

        if page != count_page and end_offset < count_page:
            buttons_row.append(InlineKeyboardButton(text="➡️",callback_data=f"sc_page_{page + 1}",))

        builder.row(*buttons_row)

        builder.row(InlineKeyboardButton(text="❌",callback_data=f"delete_sc_pagination",))

        return builder.as_markup()

    @staticmethod
    async def get_paginated_kb_responsible_scs(scs: list, page: int = 0) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        start_offset = page * 10
        end_offset = start_offset + 10
        count_page = len(scs)

        for elem in scs[start_offset:end_offset]:
            sc = Helpers._deserialize_sc(elem)
            if not sc:
                continue
            builder.row(InlineKeyboardButton(
                text=f"({sc.get('number')}) {sc.get('shortDescription', '')}",
                callback_data=f"show_sc${sc.get('number')}"
            ))

        buttons_row = []

        if page > 0:
            buttons_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"responsible_sc_page_{page - 1}", ))

        if page != count_page and end_offset < count_page:
            buttons_row.append(InlineKeyboardButton(text="➡️", callback_data=f"responsible_sc_page_{page + 1}", ))

        builder.row(*buttons_row)

        builder.row(InlineKeyboardButton(text="❌", callback_data=f"delete_responsible_sc_pagination", ))

        return builder.as_markup()

    @staticmethod
    async def get_paginated_kb_teams(teams: list, page: int = 0) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        start_offset = page * 10
        end_offset = start_offset + 10
        count_page = len(teams)

        for elem in teams[start_offset:end_offset]:
            # Проверяем, является ли elem уже словарем или строкой JSON
            if isinstance(elem, dict):
                team = elem
            else:
                team = json.loads(elem)
            builder.row(InlineKeyboardButton(
                text=team["responsibleTeamTitle"],
                callback_data=f"select_team${team['responsibleTeamId']}"
            ))

        buttons_row = []

        if page > 0:
            buttons_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"teams_page_{page - 1}", ))

        if page != count_page and end_offset < count_page:
            buttons_row.append(InlineKeyboardButton(text="➡️", callback_data=f"teams_page_{page + 1}", ))

        builder.row(*buttons_row)

        builder.row(InlineKeyboardButton(text="❌", callback_data=f"delete_teams_pagination", ))

        return builder.as_markup()

    @staticmethod
    async def get_paginated_kb_employees(employees: list, page: int = 0) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        start_offset = page * 10
        end_offset = start_offset + 10
        count_page = len(employees)

        for elem in employees[start_offset:end_offset]:
            # Проверяем, является ли elem уже словарем или строкой JSON
            if isinstance(elem, dict):
                employee = elem
            else:
                employee = json.loads(elem)
            builder.row(InlineKeyboardButton(
                text=employee["responsibleEmployeeTitle"],
                callback_data=f"select_employee${employee['responsibleEmployeeId']}"
            ))

        buttons_row = []

        if page > 0:
            buttons_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"employees_page_{page - 1}", ))

        if page != count_page and end_offset < count_page:
            buttons_row.append(InlineKeyboardButton(text="➡️", callback_data=f"employees_page_{page + 1}", ))

        builder.row(*buttons_row)

        # Добавляем кнопку "Назад к подразделениям"
        builder.row(InlineKeyboardButton(text="Назад к подразделениям ⬅️", callback_data="back_to_teams"))

        # Добавляем кнопку "Назначить на подразделение"
        builder.row(InlineKeyboardButton(text="Назначить на подразделение 🏢", callback_data="assign_to_team"))

        builder.row(InlineKeyboardButton(text="❌", callback_data=f"delete_employees_pagination", ))

        return builder.as_markup()

    @staticmethod
    async def get_paginated_kb_marketing_subdivisions(subdivisions: list, page: int = 0) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()

        start_offset = page * 10
        end_offset = start_offset + 10
        count_page = len(subdivisions)

        for i, subdivision in enumerate(subdivisions[start_offset:end_offset]):
            # Используем глобальный индекс для callback data
            global_index = start_offset + i
            
            # Правильно обрабатываем кодировку
            if isinstance(subdivision, str):
                # Если это строка, пытаемся декодировать из unicode escape
                try:
                    # Проверяем, содержит ли строка unicode escape последовательности
                    if '\\u' in subdivision:
                        subdivision = subdivision.encode().decode('unicode_escape')
                except:
                    pass  # Если не получается декодировать, используем как есть
            
            builder.row(InlineKeyboardButton(
                text=subdivision,
                callback_data=f"select_sub_{global_index}"
            ))

        buttons_row = []

        if page > 0:
            buttons_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"subdivisions_page_{page - 1}", ))

        if page != count_page and end_offset < count_page:
            buttons_row.append(InlineKeyboardButton(text="➡️", callback_data=f"subdivisions_page_{page + 1}", ))

        builder.row(*buttons_row)

        builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_services", ))
        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_marketing", ))

        return builder.as_markup()

    @staticmethod
    def delete_html_tags_from_text(text: str) -> str:
        s = MLStripper()
        s.feed(text)
        return s.get_data()
