from aiogram import types


class DTORequest:
    def __init__(self, message: types.Message, part_number: str):
        self.code_for_looking = part_number
        self.telegram_user_id = message.from_user.id
