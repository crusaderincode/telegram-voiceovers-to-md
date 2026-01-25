"""Logging configuration"""
import sys
from loguru import logger
from config.settings import Settings


def setup_logging():
    """Настройка логирования для приложения"""
    
    # Удаляем дефолтный handler
    logger.remove()
    
    # Console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=Settings.LOG_LEVEL,
        colorize=True
    )
    
    # File handler - ежедневная ротация
    logger.add(
        Settings.LOGS_DIR / "bot_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="30 days",
        level=Settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        encoding="utf-8"
    )
    
    # Error log - только ошибки
    logger.add(
        Settings.LOGS_DIR / "errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}",
        encoding="utf-8"
    )
    
    logger.info("Logging system initialized")
    return logger
