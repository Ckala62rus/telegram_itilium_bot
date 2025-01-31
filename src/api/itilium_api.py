import json
import logging
import httpx
from aiogram import types
from aiogram.types import Message, CallbackQuery
from httpx import Response

from api.urls import ApiUrls
from config.configuration import settings
from utils.helpers import Helpers

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
            message: Message | CallbackQuery,
            attribute_code='telegram'
    ) -> dict | None:
        """
        Метод поиска сотрудника на стенде ITILIUM по Telegram user_id или nickname
        :param message: обьект Aiogram
        :param attribute_code: Атрибут для 1С Итилиум (обязательный параметр)
        :return: возвращает json-объект типа employee$employee или null
        """
        post_data = {attribute_code: message.from_user.id}

        response: Response = await ItiliumBaseApi.send_request("POST", ApiUrls.FIND_EMPLOYEE_URL, post_data)

        logger.debug(f"response code: {response.status_code} | response text: {response.text}")

        if ItiliumBaseApi.check_response(response.status_code) == 1 and len(response.text) != 0:
            return json.loads(response.text)
        else:
            await message.answer(f"Вы отсутствуете в Итилиуме. "
                                 f"Сообщите администратору ваш id {message.from_user.id} для добавления")
            return None

    @staticmethod
    async def create_new_sc(data: dict) -> Response:
        """
        Метод для создания нового обращения
        :params data: словарь с данными
        "return": Response httpx. Ответ с 1С Итилиум
        """

        logger.debug(f"send data {data}")

        request_data = {
            "client": data["UUID"],
            "shorDescription": Helpers.prepare_short_description_for_sc(data['Description']),
            "Description": data['Description']
        }

        return await ItiliumBaseApi.send_request("POST", ApiUrls.CREATE_SC, request_data)

    @staticmethod
    async def send_request(method: str, url: str, data: dict | None) -> Response:
        """
        Базовый метод, обёртка над httpx
        """
        try:
            async with httpx.AsyncClient() as client:
                return httpx.request(
                    method=method,
                    url=settings.ITILIUM_TEST_URL + url,
                    data=data,
                    auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD),
                    timeout=30.0
                )
        except Exception as e:
            logger.exception(e)

    @staticmethod
    async def accept_callback_handler(callback: types.CallbackQuery) -> Response:
        return await ItiliumBaseApi._accept_or_reject_callback(callback, "accept")

    @staticmethod
    async def reject_callback_handler(callback: types.CallbackQuery) -> Response:
        return await ItiliumBaseApi._accept_or_reject_callback(callback, "reject")

    @staticmethod
    async def _accept_or_reject_callback(callback: types.CallbackQuery, state: str) -> Response:
        """
        Метод для согласования или отклонения обращения
        :state: "accept" or "reject"
        """
        return await (ItiliumBaseApi
                      .send_request("POST", ApiUrls.ACCEPT_OR_REJECT.format(
            telegram_user_id=callback.from_user.id,
            vote_number=callback.data[7:],
            state=state
        ), None))

    @staticmethod
    async def find_sc_by_id(telegram_user_id: int, sc_number: str) -> Response:
        return await (ItiliumBaseApi
        .send_request(
            "POST",
            ApiUrls.FIND_SC.format(
                telegram_user_id=telegram_user_id,
                sc_number=sc_number
            ),
            None
        ))
