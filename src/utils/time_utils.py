import datetime


class DateHelper:
    @staticmethod
    def get_current_date() -> datetime.date:
        """
        Get current date

        :return:
        """
        return datetime.datetime.now()

    @staticmethod
    def date_to_string(date, time_format: str = "%Y-%m-%d %H-%M-%S") -> str:
        """
        Converts datetime to string.
        Format by default ( 2000-12-31 23:59:00 "%Y-%m-%d %H:%M:%S" )

        https://docs.python.org/3/library/datetime.html

        :param date:
        :param time_format:
        :return:
        """
        return date.strftime(time_format)

    @staticmethod
    def string_to_date(date_string: str, time_format: str = "%Y-%m-%d %H-%M-%S") -> datetime.datetime:
        """
        Convert string date to datetime
        Format by default ( 2000-12-31 23:59:00  "%Y-%m-%d %H:%M:%S" )

        https://docs.python.org/3/library/datetime.html

        :param date_string:
        :param time_format:
        :return:
        """
        return datetime.datetime.strptime(
            date_string, time_format
        )

    @staticmethod
    def date_was_expired(date: str) -> bool:
        dat_from_inline = DateHelper.string_to_date(date)
        seconds = (datetime.datetime.now() - dat_from_inline).total_seconds()
        return seconds > 20
