from datetime import datetime
import logging

from api.itilium_api import ItiliumBaseApi

logger = logging.getLogger(__name__)


class BotUser:
    # default constructor
    def __init__(self, user_id, chat_id=None, user_nickname=None):
        # общие параметры объекта, описывающего контекст взаимодейсвия пользователя с ботом: nickname и его chat_id
        self.employee_nickname = user_nickname
        self.employee_chat_id = chat_id

        # дата и время последнего обновления данных. используется как дата и время для проверки таймаута
        self.last_update_time = datetime.now()

        # общие данные о пользователе из ITILIUM
        self.__base_work = ItiliumBaseApi()

        self.full_user_data = self.__base_work.get_employee_data_by_identifier(user_id)

        del self.__base_work
        self.user_system_info = {
            # заявки сотрудника/ в отвественности/ подписки/ в отделе/ в команде
            "empl_scs": list(self.full_user_data["servicecalls"]),
            "sc_type": None,
            # активные согласования сотрудника
            "empl_negs": list(),
            # идентификатор заявки, к которой будет добавлен комментарий
            "sc_to_reply_id": None,
            # идентификатор голосования, к которому будет добавлено замечание
            "vote_to_reply_id": None,
            # идентификатор последнего "ключевого" (опроного) сообщения
            "last_mes_id": None
        }

        # список идентификаторов сообщений, которые были созданы в сеансе взаимодействия с ботом
        self.current_session_mes_id_list = []

        # параметры просматриваемой заявки (ее UUID, дедлайн, статус, идентификаторы сообщений с комментариями,
        # заявка находится в ответственности, список задач в рамках заявки, идентификаторы сообщений с заявками
        self.viewed_sc_or_task = {
            "UUID": "",
            "deadLineTime": "",
            "state": "",
            "vo_comments_mes_id": [],
            "in_responsible": False,
            "in_subscriptions": False,
            "tasks_list": [],
            "tasks_mes_id": [],
            "docs_mes_id": []
        }

        # идентификатор последнего "ключевого" (опорного) сообщения
        # self.last_message_id = None
        # идентификаторы состояния взаимодействия (можжно вводить заявку/комментарий/описание задачи и тд)
        self.message_states = {"no_message": 0, "service_call": 1, "comment": 2, "neg_employee_surname": 3,
                               "neg_description": 4, "task_description": 5, "task_deadline": 6, "deferred_to": 7,
                               "comment_reply": 8, "vote_reply": 9, "sc_search": 10}
        self.current_mes_state = 1

        # параметры новой создаваемой задачи
        self.new_task_for_sc = {
            # "author": self.user_system_info["empl_uuid"],
            "serviceCall": "", "description": "",
            "responsibleTeam": "", "deadline": ""
        }

        # вспомогательные атрибуты для хранения списка ответсвенных команд и идентификаторов сообщений для удаления
        self.team_list = {}
        self.team_list_prep = list()
        self.task_mes_id = []

        # параметры нового создаваемого согласования
        self.negotiation = {"sourceR": "", "cabEmployee": [], "description": "", "negType": "", "sc_description": ""}
        self.employee_neg_list = {}
