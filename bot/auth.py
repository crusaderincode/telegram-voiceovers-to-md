"""User authorization"""
from loguru import logger
from telegram import Update
from telegram.ext import filters

from config.settings import Settings


def is_authorized(user_id: int) -> bool:
    """
    Проверка авторизации пользователя
    
    Args:
        user_id: Telegram User ID
        
    Returns:
        bool: Авторизован ли пользователь
    """
    authorized = user_id == Settings.ALLOWED_USER_ID
    
    if not authorized:
        logger.warning(f"Unauthorized access attempt from user {user_id}")
    
    return authorized


def is_authorized_update(update: Update) -> bool:
    """
    Проверка авторизации из Update
    
    Args:
        update: Telegram Update
        
    Returns:
        bool: Авторизован ли пользователь
    """
    if not update.effective_user:
        return False
    
    return is_authorized(update.effective_user.id)


# Filter для использования в handlers
authorized_filter = filters.User(user_id=Settings.ALLOWED_USER_ID)
