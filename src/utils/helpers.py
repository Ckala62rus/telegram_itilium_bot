import logging

from aiogram.types import Message
from aiogram import Bot


logger = logging.getLogger(__name__)


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
        if input_data["responsibleEmployeeTitle"] is not None:
            sc_attr["responsibleEmployee"] += input_data["responsibleEmployeeTitle"]
        # Срок решения заявки
        if input_data["deadlineDate"] is not None:
            # date = datetime.strptime(input_data["timeAllowanceTimer"]["deadLineTime"].replace('.', '-'),
            #                          "%Y-%m-%d %H:%M:%S") + timedelta(hours=3)
            # date.strftime("%d.%m.%Y %H:%M")
            sc_attr["deadlineDate"] += input_data["deadlineDate"]
        # Описание заявки
        sc_attr["description"] += input_data["description"]
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
