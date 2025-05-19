import asyncio
import json
import logging
import ssl

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
        try:
            post_data = {attribute_code: message.from_user.id}

            logger.debug(f"get_employee_data_by_identifier {ApiUrls.FIND_EMPLOYEE_URL}")

            response: Response = await ItiliumBaseApi.send_request("POST", ApiUrls.FIND_EMPLOYEE_URL, post_data)

            if response.status_code == httpx.codes.FORBIDDEN:
                await message.message.answer(f"Доступ запрещён.")

            logger.debug(f"response code: {response.status_code} | response text: {response.text}")
        except Exception as e:
            logger.error(e)
            await message.answer()
            await message.message.answer("1С Итилиум прислал пустой ответ. Обратитесь к администратору")
            return None

        if ItiliumBaseApi.check_response(response.status_code) == 1 and len(response.text) != 0:
            return json.loads(response.text)
        else:
            await message.answer(f"Вы отсутствуете в Итилиуме. "
                                 f"Сообщите администратору ваш id {message.from_user.id} для добавления")
            return None

    @staticmethod
    async def create_new_sc(data: dict, files: list) -> Response:
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

        url = ApiUrls.CREATE_SC

        # if len(files) > 0:
        #     url += "?"
        #     url_params = ";".join(files)
        #     url += f"files={url_params}"
        #
        # logger.debug(f"url: {url}")

        if len(files) > 0:
            request_data["files"] = json.dumps(files)

        return await ItiliumBaseApi.send_request("POST", url, request_data)

    @staticmethod
    async def send_request(
            method: str,
            url: str,
            data: dict | None,
            params=None
    ) -> Response:
        """
        Базовый метод, обёртка над httpx
        """
        logger.debug(f"send_request {method} {settings.ITILIUM_URL + url}")
        logger.debug(f"send_request data {data}")

        try:
            async with httpx.AsyncClient() as client:
                return await client.request(
                    method=method,
                    url=settings.ITILIUM_URL + url,
                    data=data,
                    auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD),
                    timeout=30.0,
                    params=params
                )
        except Exception as e:
            logger.debug(f"error for {method} {url} {data}")
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
        response = await (ItiliumBaseApi
                          .send_request("POST", ApiUrls.ACCEPT_OR_REJECT.format(
            telegram_user_id=callback.from_user.id,
            vote_number=callback.data[7:],
            state=state
        ), None))

        await callback.message.edit_reply_markup()

        return response

    @staticmethod
    async def find_sc_by_id(telegram_user_id: int, sc_number: str) -> Response | None:
        # try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(settings.ITILIUM_URL + ApiUrls.FIND_SC.format(
                telegram_user_id=telegram_user_id,
                sc_number=sc_number
            ), auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD), timeout=30.0)

            logger.debug(f"response code: {resp.status_code} | response text: {resp.text}")

            if resp.status_code == httpx.codes.OK and len(resp.text) > 0:
                return resp.json()

    # except Exception as e:
    #     logger.debug(f"error for {telegram_user_id} {sc_number} {e}")
    #     logger.exception(e)
    #     return None

    @staticmethod
    async def get_task_for_async_find_sc_by_id(scs: list, callback: CallbackQuery):
        tasks = [asyncio.create_task(ItiliumBaseApi.find_sc_by_id(callback.from_user.id, sc)) for sc in scs]
        return await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def add_comment_to_sc(
            telegram_user_id: int,
            comment: str,
            sc_number: str,
            files: list
    ) -> Response:
        logger.info(f"added new comment sc {sc_number} | telegram_user_id: {telegram_user_id} | comment: {comment}")

        url = ApiUrls.ADD_COMMENT_TO_SC.format(
            telegram_user_id=telegram_user_id,
            source=sc_number,
            comment_text=comment
        )

        logger.debug(f"url: {url}")
        logger.debug(f"comment: {comment}")

        data: dict | None = None

        if len(files) > 0:
            url_params = ";".join(files)
            url += f"&files={url_params}"
            logger.debug(f"url: {url}")

            # data = dict()
            # data["files"] = json.dumps(files)
            # logger.debug(f"files to send itilium > {json.dumps(files)}")

        return await (ItiliumBaseApi
        .send_request(
            "POST",
            url,
            data
        ))

    @staticmethod
    async def confirm_sc(
            telegram_user_id: int,
            sc_number: str,
            mark: str,
            comment: str | None
    ) -> Response:
        """
        Метод отправляет оценку пользователя, от 0 до 5 для оценки решённой задачи.
        Комментарий, является опциональным
        """

        url = ApiUrls.CONFIRM_SC.format(
            telegram_user_id=telegram_user_id,
            incident=sc_number,
            mark=mark,
        )

        if comment:
            url += f"&comment_text={comment}"

        return await (ItiliumBaseApi.send_request("GET", url, None))

    @staticmethod
    async def scs_responsibility_tasks(telegram_user_id: int) -> Response:
        url = ApiUrls.SCS_RESPONSIBLE.format(
            telegram_user_id=telegram_user_id,
        )

        return await (ItiliumBaseApi.send_request("POST", url, None))

    @staticmethod
    async def change_sc_state(
            telegram_user_id: int,
            sc_number: str,
            state: str,
    ) -> Response:
        url = ApiUrls.CHANGE_STATE_SC.format(
            telegram_user_id=telegram_user_id,
            inc_number=sc_number,
            new_state=state
        )

        return await (ItiliumBaseApi.send_request("POST", url, None))

    @staticmethod
    async def change_sc_state_with_comment(
            telegram_user_id: int,
            sc_number: str,
            state: str,
            date_inc: str,
            comment: str,
    ) -> Response:
        url = ApiUrls.CHANGE_STATE_SC_WITH_COMMENT.format(
            telegram_user_id=telegram_user_id,
            inc_number=sc_number,
            new_state=state,
            date_inc=date_inc,
            comment=comment,
        )

        return await (ItiliumBaseApi.send_request("POST", url, None))
