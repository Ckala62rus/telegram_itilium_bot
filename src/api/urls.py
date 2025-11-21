from config.configuration import settings
from utils.logger_project import setup_logger

logger = setup_logger(__name__)


class ApiUrls:
    baseUrl: str = "settings.LARAVEL_API_URL"
    executeCommand: str = 'find-party'

    FIND_EMPLOYEE_URL: str = "find_employee"
    # CREATE_SC: str = "/create_sc?"
    CREATE_SC: str = "create_sc"
    REGISTRATION: str = "registration"
    ACCEPT_OR_REJECT: str = "vote_change?telegram={telegram_user_id}&vote_number={vote_number}&state={state}"
    FIND_SC: str = "find_sc?telegram={telegram_user_id}&sc_number={sc_number}"
    ADD_COMMENT_TO_SC: str = "add_comment?telegram={telegram_user_id}&source={source}&source_type=servicecall&comment_text={comment_text}"
    CONFIRM_SC: str = "confirm_sc?telegram={telegram_user_id}&incident={incident}&mark={mark}"
    SCS_RESPONSIBLE: str = "list_sc_responsible?telegram={telegram_user_id}"
    CHANGE_STATE_SC: str = "change_state_sc?telegram={telegram_user_id}&inc_number={inc_number}&new_state={new_state}"
    CHANGE_STATE_SC_WITH_COMMENT: str = ("change_state_sc?"
                                         "telegram={telegram_user_id}"
                                         "&inc_number={inc_number}"
                                         "&new_state={new_state}"
                                         "&date_inc={date_inc}"
                                         "&comment={comment}"
                                         )
    GET_RESPONSIBLES: str = "responsibles_sc?telegram={telegram_user_id}&sc_number={sc_number}"
    CHANGE_RESPONSIBLE: str = "change_responsible_sc?telegram={telegram_user_id}&inc_number={inc_number}&responsibleEmployeeId={responsible_employee_id}"
    
    # Маркетинговые заявки
    CREATE_SC_MARKETING: str = "create_sc_Marketing"


apiUrls = ApiUrls()
