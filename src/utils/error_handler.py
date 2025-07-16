import logging
import traceback
from typing import Optional, Callable, Any
from functools import wraps

from aiogram.types import Message, CallbackQuery
from aiogram import Bot

from utils.message_templates import MessageTemplates

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Централизованная система обработки ошибок"""
    
    @staticmethod
    def handle_api_error(error: Exception, context: str = "") -> str:
        """Обрабатывает ошибки API и возвращает понятное сообщение"""
        error_msg = str(error).lower()
        
        if "timeout" in error_msg or "connection" in error_msg:
            return "Сервер временно недоступен. Попробуйте позже."
        elif "unauthorized" in error_msg or "401" in error_msg:
            return "Ошибка авторизации. Обратитесь к администратору."
        elif "not found" in error_msg or "404" in error_msg:
            return "Запрашиваемые данные не найдены."
        elif "validation" in error_msg or "400" in error_msg:
            return "Некорректные данные. Проверьте введенную информацию."
        elif "server" in error_msg or "500" in error_msg:
            return "Ошибка сервера. Попробуйте позже."
        else:
            logger.error(f"Неизвестная ошибка API в {context}: {error}")
            return "Произошла неизвестная ошибка. Попробуйте позже."
    
    @staticmethod
    def handle_database_error(error: Exception, context: str = "") -> str:
        """Обрабатывает ошибки базы данных"""
        error_msg = str(error).lower()
        
        if "connection" in error_msg:
            return "Ошибка подключения к базе данных."
        elif "timeout" in error_msg:
            return "Превышено время ожидания ответа от базы данных."
        else:
            logger.error(f"Ошибка базы данных в {context}: {error}")
            return "Ошибка работы с базой данных."
    
    @staticmethod
    def handle_telegram_error(error: Exception, context: str = "") -> str:
        """Обрабатывает ошибки Telegram API"""
        error_msg = str(error).lower()
        
        if "bot was blocked" in error_msg:
            return "Бот заблокирован пользователем."
        elif "message is not modified" in error_msg:
            return "Сообщение не изменилось."
        elif "message to edit not found" in error_msg:
            return "Сообщение для редактирования не найдено."
        else:
            logger.error(f"Ошибка Telegram API в {context}: {error}")
            return "Ошибка взаимодействия с Telegram."
    
    @staticmethod
    async def send_error_message(
        bot: Bot,
        chat_id: int,
        error: Exception,
        context: str = "",
        show_traceback: bool = False
    ):
        """Отправляет сообщение об ошибке пользователю"""
        try:
            # Определяем тип ошибки и получаем понятное сообщение
            if "api" in context.lower():
                user_message = ErrorHandler.handle_api_error(error, context)
            elif "database" in context.lower() or "db" in context.lower():
                user_message = ErrorHandler.handle_database_error(error, context)
            elif "telegram" in context.lower():
                user_message = ErrorHandler.handle_telegram_error(error, context)
            else:
                user_message = "Произошла ошибка. Попробуйте позже."
            
            # Отправляем сообщение пользователю
            await bot.send_message(
                chat_id=chat_id,
                text=user_message
            )
            
            # Логируем ошибку
            logger.error(f"Ошибка в {context}: {error}")
            if show_traceback:
                logger.error(f"Traceback: {traceback.format_exc()}")
                
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")


def handle_errors(
    context: str = "",
    show_traceback: bool = False,
    default_message: str = "Произошла ошибка. Попробуйте позже."
):
    """Декоратор для обработки ошибок в обработчиках"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as error:
                # Извлекаем bot и chat_id из аргументов
                bot = None
                chat_id = None
                
                for arg in args:
                    if isinstance(arg, Message):
                        bot = arg.bot
                        chat_id = arg.chat.id
                        break
                    elif isinstance(arg, CallbackQuery):
                        bot = arg.bot
                        chat_id = arg.message.chat.id
                        break
                
                # Логируем ошибку
                logger.error(f"Ошибка в {func.__name__} ({context}): {error}")
                if show_traceback:
                    logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Отправляем сообщение об ошибке
                if bot and chat_id:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=default_message
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
                
                # Возвращаем None или пустой результат
                return None
        
        return wrapper
    return decorator


def handle_api_errors(func: Callable) -> Callable:
    """Декоратор для обработки ошибок API"""
    return handle_errors(
        context="API",
        default_message="Ошибка при обращении к серверу. Попробуйте позже."
    )(func)


def handle_database_errors(func: Callable) -> Callable:
    """Декоратор для обработки ошибок базы данных"""
    return handle_errors(
        context="Database",
        default_message="Ошибка работы с базой данных. Попробуйте позже."
    )(func)


def handle_telegram_errors(func: Callable) -> Callable:
    """Декоратор для обработки ошибок Telegram API"""
    return handle_errors(
        context="Telegram",
        default_message="Ошибка взаимодействия с Telegram. Попробуйте позже."
    )(func) 