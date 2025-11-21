import asyncio
import json
import logging

import httpx
from aiogram import types
from aiogram.types import Message, CallbackQuery
from httpx import Response

from api.urls import ApiUrls
from config.configuration import settings
from utils.helpers import Helpers
from utils.http_client import log_and_request

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
    async def find_employee_by_attribute(
            identifier: int,
            attribute_code: str = 'telegram'
    ) -> Response:
        """
        Базовый метод запроса find_employee с логированием.
        """
        payload = {attribute_code: identifier}
        logger.info("Делаем запрос в Итилиум find_employee с параметрами: %s", payload)
        response = await ItiliumBaseApi.send_request("POST", ApiUrls.FIND_EMPLOYEE_URL, payload)
        logger.info(
            "Пришел ответ find_employee. Код: %s | Тело: %s",
            response.status_code,
            response.text
        )
        return response

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
            response: Response = await ItiliumBaseApi.find_employee_by_attribute(
                identifier=message.from_user.id,
                attribute_code=attribute_code
            )

            logger.debug(f"response code: {response.status_code} | response text: {response.text}")

            if response.status_code == httpx.codes.OK and len(response.text) != 0:
                try:
                    return json.loads(response.text)
                except json.JSONDecodeError as decode_error:
                    logger.error(f"Не удалось преобразовать ответ find_employee: {decode_error}")
                    return None

            logger.debug("Empty or invalid response from Itilium")
            return None
        except Exception as e:
            logger.error(e)
            # Пробрасываем ошибку для обработки в handlers
            raise

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

        if len(files) > 0:
            request_data["files"] = json.dumps(files)

        return await ItiliumBaseApi.send_request("POST", url, request_data)

    @staticmethod
    async def create_registration_request(data: dict) -> Response:
        """
        Создание заявки на регистрацию пользователя.
        """
        logger.info("Делаем запрос в Итилиум registration с параметрами: %s", data)
        response = await ItiliumBaseApi.send_request("POST", ApiUrls.REGISTRATION, data)
        logger.info(
            "Пришел ответ registration. Код: %s | Тело: %s",
            response.status_code,
            response.text
        )
        return response

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
            response = await log_and_request(
                method=method,
                url=settings.ITILIUM_URL + url,
                data=data,
                params=params,
                auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD)
            )
            return response
        except Exception as e:
            logger.debug(f"error for {method} {url} {data}")
            logger.exception(e)
            raise

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
        try:
            resp = await log_and_request(
                method="POST",
                url=settings.ITILIUM_URL + ApiUrls.FIND_SC.format(
                    telegram_user_id=telegram_user_id,
                    sc_number=sc_number
                ),
                auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD)
            )

            logger.debug(f"response code: {resp.status_code} | response text: {resp.text}")

            if resp.status_code == httpx.codes.OK and len(resp.text) > 0:
                return resp.json()
        except Exception as e:
            logger.debug(f"error for {telegram_user_id} {sc_number} {e}")
            logger.exception(e)
            return None

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

        return await (ItiliumBaseApi.send_request("POST", url, None))

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

    @staticmethod
    async def get_responsibles(
            telegram_user_id: int,
            sc_number: str
    ) -> Response:
        """
        Метод для получения списка ответственных для заявки
        """
        url = ApiUrls.GET_RESPONSIBLES.format(
            telegram_user_id=telegram_user_id,
            sc_number=sc_number
        )

        return await (ItiliumBaseApi.send_request("POST", url, None))

    @staticmethod
    async def change_responsible(
            telegram_user_id: int,
            sc_number: str,
            responsible_employee_id: str
    ) -> Response:
        """
        Метод для смены ответственного за заявку
        """
        url = ApiUrls.CHANGE_RESPONSIBLE.format(
            telegram_user_id=telegram_user_id,
            inc_number=sc_number,
            responsible_employee_id=responsible_employee_id
        )

        return await (ItiliumBaseApi.send_request("POST", url, None))

    @staticmethod
    async def get_marketing_services(telegram_id: int) -> list | None:
        """
        Получение списка сервисов маркетинга
        :param telegram_id: ID пользователя в Telegram
        :return: список сервисов или None
        """
        try:
            url = f"{settings.ITILIUM_URL}/listServicesMarketing"
            params = {"telegram": telegram_id}
            
            response = await log_and_request(
                method="GET",
                url=url,
                params=params,
                auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD)
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Marketing services: {data}")
                return data
            else:
                logger.error(f"Failed to get marketing services: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting marketing services: {e}")
            return None

    @staticmethod
    async def get_marketing_subdivisions(telegram_id: int) -> list | None:
        """
        Получение списка подразделений для маркетинга
        :param telegram_id: ID пользователя в Telegram
        :return: список подразделений или None
        """
        try:
            url = f"{settings.ITILIUM_URL}/listSubdivisionMarketing"
            params = {"telegram": telegram_id}
            logger.info(f"Requesting marketing subdivisions for user {telegram_id}")
            logger.info(f"URL: {url}")
            logger.info(f"Params: {params}")
            
            response = await log_and_request(
                method="GET",
                url=url,
                params=params,
                auth=(settings.ITILIUM_LOGIN, settings.ITILIUM_PASSWORD)
            )
            
            logger.info(f"Response status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Marketing subdivisions received: {len(data) if data else 0} items")
                logger.debug(f"Marketing subdivisions data: {data}")
                return data
            else:
                logger.error(f"Failed to get marketing subdivisions: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting marketing subdivisions: {e}")
            return None
    
    @staticmethod
    async def create_marketing_request(
        telegram_id: int,
        service: str,
        subdivision: str,
        execution_date: str,
        form_data: dict,
        files: list = None
    ) -> Response:
        """
        Создание маркетинговой заявки
        
        :param telegram_id: ID пользователя в Telegram
        :param service: Название услуги (Дизайн, Мероприятие, и т.д.)
        :param subdivision: Название подразделения
        :param execution_date: Дата исполнения (формат DD.MM.YYYY)
        :param form_data: Данные формы (зависят от типа услуги)
        :param files: Список файлов
        :return: Response от API
        """
        try:
            # Формируем данные запроса
            request_data = {
                "telegram": telegram_id,
                "Services": service,
                "Subdivision": subdivision,
                "ExecutionDate": execution_date,
            }
            
            # Добавляем данные формы в зависимости от типа услуги
            if service == "Дизайн":
                request_data.update({
                    "LayoutName": form_data.get("layout_name", ""),
                    "Size": form_data.get("dimensions", ""),
                    "ForWhat": form_data.get("purpose", ""),
                    "RequiredText": form_data.get("required_text", ""),
                    "LayoutFormats": form_data.get("formats", ""),
                })
            elif service == "Мероприятие":
                request_data.update({
                    "ThemeEvent": form_data.get("event_theme", ""),
                    "Description": form_data.get("description", ""),
                    "Budget": form_data.get("budget", ""),
                })
                if "free_text" in form_data:
                    request_data["Description"] = form_data.get("free_text", "")
            else:  # Реклама, SMM, Акция, Иное
                request_data.update({
                    "Description": form_data.get("free_text", ""),
                })
            
            # Добавляем файлы
            if files:
                request_data["files"] = json.dumps(files)
            
            logger.info(f"Creating marketing request for user {telegram_id}")
            logger.debug(f"Request data: {request_data}")
            
            # Отправляем запрос
            response = await ItiliumBaseApi.send_request(
                method="POST",
                url=ApiUrls.CREATE_SC_MARKETING,
                data=request_data
            )
            
            logger.info(f"Marketing request response status: {response.status_code}")
            logger.debug(f"Marketing request response: {response.text}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error creating marketing request: {e}")
            raise