class Helpers:

    def prepare_short_description_for_sc(sc_description):
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
