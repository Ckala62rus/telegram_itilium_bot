from enum import StrEnum
from typing import Dict, Any


class MessageTemplates(StrEnum):
    # Общие сообщения
    ACTIONS_CANCELED = "Действия отменены"
    ACTIONS_CANCELED_SIMPLE = "действия отменены"
    ACCESS_DENIED = "Доступ запрещён."
    ITILIUM_EMPTY_RESPONSE = "1С Итилиум прислал пустой ответ. Обратитесь к администратору. Попробуйте еще раз."
    ITILIUM_ERROR = "При запросе в Итилиум произошла ошибка"
    CONTACT_ADMIN = "Обратитесь к администратору"
    
    # Сообщения о заявках
    ENTER_ISSUE_DESCRIPTION = "Введите описание обращения"
    ISSUE_CREATED_SUCCESS = "Ваша завка успешно создана!"
    ISSUE_CREATION_ERROR = "Не удалось создать заявку. Ошибка сервера {error}\n\rПовотрите попытку позже"
    ISSUE_NOT_FOUND = "Заявка с номером {sc_number} не найдена"
    ISSUE_SEARCH_ERROR = "Ошибка при поиске заявки {error}"
    ISSUE_SEARCH_RESULT = "Поиск заявки {sc_number}. {result}"
    ISSUE_LOOKING = "Ищу заявку с номером"
    ENTER_ISSUE_NUMBER = "Введите номер заявки для поиска или нажмите кнопку 'отмена'"
    
    # Сообщения о согласовании
    AGREED = "Согласовано"
    AGREEMENT_ERROR = "Во время согласования, произошла ошибка. Обратитесь к администратору"
    
    # Сообщения о загрузке
    LOADING_REQUESTS = "Запрашиваю заявки, подождите..."
    NO_CREATED_ISSUES = "У вас нет созданных заявок заявок"
    NO_RESPONSIBLE_ISSUES = "У вас нет заявок в ответственности"
    
    # Сообщения о пользователях
    USER_NOT_FOUND_ITILIUM = "Вы отсутствуете в Итилиуме. Сообщите администратору ваш id {user_id} для добавления"
    USER_ALREADY_EXISTS = "Вы уже есть в системе"
    PHONE_REQUIRED = ("Для того, что бы пользоваться ботом, "
                     "вам необходимо поделиться номером телефона и "
                     "сообщить администратору, для добавления прав")
    
    # Сообщения о меню
    CHOOSE_MENU_ITEM = "Выберите необходимый пункт меню:"
    YOUR_REQUESTS = "Ваши обращения"
    RESPONSIBLE_REQUESTS = "Обращения в вашей ответственности"
    
    # Сообщения об оценке
    YOUR_GRADE = "Ваша оценка: {grade}."
    GRADE_COMMENT_REQUIRED = "С оценкой ({grade}), комментарий обязателен!. \nВведите коментарий или отмените действия"
    
    # Сообщения админа
    ENTER_PHONE_FOR_ADMIN = "Введите номер телефон для поиска ( пример: +78005553535 )"
    
    # Кнопки
    HIDE_INFO = "Скрыть информацию ↩️"
    CHANGE_STATUS = "Поменять статус 🔁"
    CANCEL_BUTTON = "отмена ❌"
    ADD_COMMENT = "добавить комментарий 📃"
    SEND_GRADE = "отправить оценку 📩"


class ButtonTemplates:
    """Шаблоны для кнопок"""
    
    @staticmethod
    def hide_info() -> Dict[str, str]:
        return {MessageTemplates.HIDE_INFO: "del_message"}
    
    @staticmethod
    def hide_and_change_status(sc_number: str) -> Dict[str, str]:
        return {
            MessageTemplates.HIDE_INFO: "del_message",
            MessageTemplates.CHANGE_STATUS: f"show_state${sc_number}"
        }
    
    @staticmethod
    def cancel() -> Dict[str, str]:
        return {MessageTemplates.CANCEL_BUTTON: "cancel"}
    
    @staticmethod
    def grade_actions() -> Dict[str, str]:
        return {
            MessageTemplates.CANCEL_BUTTON: "cancel",
            MessageTemplates.ADD_COMMENT: "add_confirm_sc_comment",
            MessageTemplates.SEND_GRADE: "send_confirm_sc"
        }


class MessageFormatter:
    """Форматирование сообщений с подстановкой переменных"""
    
    @staticmethod
    def format(template: str, **kwargs: Any) -> str:
        """Форматирует шаблон сообщения с подстановкой переменных"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # Если не хватает переменной, возвращаем шаблон как есть
            return template
    
    @staticmethod
    def issue_not_found(sc_number: str) -> str:
        return MessageFormatter.format(MessageTemplates.ISSUE_NOT_FOUND, sc_number=sc_number)
    
    @staticmethod
    def user_not_found_itilium(user_id: int) -> str:
        return MessageFormatter.format(MessageTemplates.USER_NOT_FOUND_ITILIUM, user_id=user_id)
    
    @staticmethod
    def issue_creation_error(error: str) -> str:
        return MessageFormatter.format(MessageTemplates.ISSUE_CREATION_ERROR, error=error)
    
    @staticmethod
    def issue_search_error(error: str) -> str:
        return MessageFormatter.format(MessageTemplates.ISSUE_SEARCH_ERROR, error=error)
    
    @staticmethod
    def issue_search_result(sc_number: str, result: str) -> str:
        return MessageFormatter.format(MessageTemplates.ISSUE_SEARCH_RESULT, sc_number=sc_number, result=result)
    
    @staticmethod
    def your_grade(grade: str) -> str:
        return MessageFormatter.format(MessageTemplates.YOUR_GRADE, grade=grade)
    
    @staticmethod
    def grade_comment_required(grade: int) -> str:
        return MessageFormatter.format(MessageTemplates.GRADE_COMMENT_REQUIRED, grade=grade) 