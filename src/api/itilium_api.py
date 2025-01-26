import json
import logging
import httpx
from aiogram.types import Message

from config.configuration import settings


logger = logging.getLogger(__name__)


class ItiliumBaseApi:
    def __init__(self):
        pass

    @staticmethod
    def check_response(response_code):
        """
        Метод проверки ответа сервера ITSM на запрос к нему
        :param response_code: ответ сервера ITSM (в виде кода)
        :return: возвращает 1, если сервер принял запрос, или -1 в противном случае
        """
        success_code = [200, 201, 204]
        if response_code in success_code:
            return 1
        else:
            return -1

    @staticmethod
    async def get_employee_data_by_identifier(
        message: Message,
        attribute_code='telegram'
    ) -> dict | None:
        """
        Метод поиска сотрудника на стенде ITILIUM по Telegram user_id или nickname
        :param message: обьект Aiogram
        :param user_id: идентификатор пользователя в Telegram
        :param attribute_code:
        :return: возвращает json-объект типа employee$employee или null
        """
        post_data = {attribute_code: message.from_user.id}

        response = httpx.post(
            # url-адрес для поиска сотрудника по его Telegram user_id
            url=settings.ITILIUM_TEST_URL + "find_employee",

            data=post_data,
            auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD)
        )

        logger.debug(f"response code: {response.status_code} | response text: {response.text}")

        if ItiliumBaseApi.check_response(response.status_code) == 1 and len(response.text) != 0:
            return json.loads(response.text)
        else:
            await message.answer(f"Вы отсутствуете в Итилиуме. "
                                 f"Сообщите администратору ваш id {message.from_user.id} для добавления")
            return None
