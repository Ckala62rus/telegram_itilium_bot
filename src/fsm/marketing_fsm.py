from aiogram.fsm.state import StatesGroup, State


class MarketingRequest(StatesGroup):
    """Состояния для создания маркетинговой заявки"""
    
    # Выбор типа заявки
    CHOOSE_REQUEST_TYPE = State()
    
    # Выбор сервиса маркетинга
    CHOOSE_SERVICE = State()
    
    # Выбор подразделения
    CHOOSE_SUBDIVISION = State()
    
    # Выбор даты исполнения
    CHOOSE_EXECUTION_DATE = State()
    
    # Заполнение формы в зависимости от номера формы
    FILL_FORM_1 = State()  # Дизайн
    FILL_FORM_2 = State()  # Мероприятие
    FILL_FORM_3 = State()  # Реклама, SMM, Акция, Иное
    
    # Загрузка файлов для дизайна
    UPLOAD_FILES = State()
    
    # Предварительный просмотр и подтверждение
    PREVIEW_REQUEST = State()
    CONFIRM_REQUEST = State()

