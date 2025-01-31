from config.configuration import settings


class ApiUrls:
    baseUrl: str = "settings.LARAVEL_API_URL"
    executeCommand: str = '/find-party'

    FIND_EMPLOYEE_URL: str = "/find_employee"
    CREATE_SC: str = "/create_sc"
    ACCEPT_OR_REJECT: str = "/vote_change?telegram={telegram_user_id}&vote_number={vote_number}&state={state}"
    FIND_SC: str = "/find_sc?telegram={telegram_user_id}&sc_number={sc_number}"


apiUrls = ApiUrls()
