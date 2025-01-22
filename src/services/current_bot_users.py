from datetime import datetime


class CurrentBotUsers:
    # default constructor
    def __init__(self):
        self.all_bot_users = dict()

    # Метод по добавлению пользователя в список пользователей бота и хранения контекста взаимодествия с ним
    # def add_new_user(self, user_id, chat_id, nickname):
    #     current_user = BotUser(user_id, chat_id, nickname)
    #     if user_id not in self.all_bot_users:
    #         self.all_bot_users[user_id] = current_user
    #     print(self.all_bot_users)

    # Метод, сохраняющий идентификаторы сообщений с сообщениями в рамках сесии пользователя
    def add_current_session_mes_id_to_list(self, user_id, mes_id):
        if user_id in self.all_bot_users:
            current_user = self.all_bot_users.get(user_id)
            current_user.current_session_mes_id_list.append(mes_id)
            current_user.last_update_time = datetime.now()
