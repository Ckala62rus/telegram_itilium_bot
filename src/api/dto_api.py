from aiogram import types
from utils.logger_project import setup_logger

logger = setup_logger(__name__)


class DTORequest:
    def __init__(self, message: types.Message, part_number: str):
        self.code_for_looking = part_number
        self.telegram_user_id = message.from_user.id
