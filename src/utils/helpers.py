class Helpers:

    def prepare_short_description_for_sc(sc_description: str):
        """
        Метод, подготавливающий тему заявки из введенного описания этой заявки. Если длина заявки более 30 символов,
        то тема формируется из первых 30 символов описания. При этом если последнее слово, взятое в тему заявки, будет
        разбито на две части, то все это слово отбрасывается. Если же длина описания заявки менее 30 символов, то
        тема заявки полностью скопирует описание заявки.
        :param sc_description: описание формируемой заявки
        :return: возвращает подготовленную тему создаваемой завки
        """
        if len(sc_description) > 30:
            words_list = sc_description.split(' ')
            short_description = ''
            for word in words_list:
                if len(short_description) + len(word) + 1 <= 31:
                    short_description = f'{short_description} {word}'
                else:
                    break
            return f'{short_description.lstrip()}...'
        else:
            return sc_description

    # Метод подготовки текста заявки. Принимает на вход:
    # param input_data - JSON-ответ с параметрами заявки
    # Функция возвращает заполненный ассоциативный массив (словарь) с данными отправляемого сообщения
    def prepare_sc(input_data: dict):
        # Создаем словарь с необходимыми атрибутами
        sc_attr = {
            "number": "<b>Заявка:</b> № ",
            "shortDescription": "<b>Тема:</b> ",
            "state": "<b>Статус:</b> ",
            "responsibleEmployee": "<b>Ответственный специалист:</b> ",
            "deadlineDate": "<b>Срок решения заявки:</b> ",
            "description": "<b>Описание:</b> ",
        }
        # Номер заявки
        sc_attr["number"] += str(input_data["number"])
        # Тема заявки
        if input_data["shortDescription"] is not None:
            sc_attr["shortDescription"] += input_data["shortDescription"]
        # Статус заявки
        sc_attr["state"] += input_data["state"]
        # Ответственный специалист
        if input_data["responsibleEmployeeTitle"] is not None:
            sc_attr["responsibleEmployee"] += input_data["responsibleEmployeeTitle"]
        # Срок решения заявки
        if input_data["deadlineDate"] is not None:
            # date = datetime.strptime(input_data["timeAllowanceTimer"]["deadLineTime"].replace('.', '-'),
            #                          "%Y-%m-%d %H:%M:%S") + timedelta(hours=3)
            # date.strftime("%d.%m.%Y %H:%M")
            sc_attr["deadlineDate"] += input_data["deadlineDate"]
        # Описание заявки
        sc_attr["description"] += input_data["description"]
        # форимируем окончательно текст отправляемого сообщения
        output_data = ''
        for key in sc_attr:
            output_data += (str(sc_attr[key]) + '\n\r')
        return output_data
