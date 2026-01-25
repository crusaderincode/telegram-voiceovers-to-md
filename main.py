#!/usr/bin/env python3
"""
AI Notes Bot - Telegram бот для создания заметок из голосовых сообщений
"""
import asyncio
import signal
import sys

from loguru import logger
from telegram.ext import Application

from config.settings import Settings
from bot import BotHandlers
from utils import setup_logging, cleanup_temp_files


def signal_handler(signum, frame):
    """Обработка сигналов завершения"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def startup():
    """Действия при запуске"""
    logger.info("=" * 60)
    logger.info("AI Notes Bot Starting...")
    logger.info("=" * 60)
    
    # Проверка конфигурации
    try:
        Settings.validate()
        logger.info("✓ Configuration validated")
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Очистка старых временных файлов
    deleted = cleanup_temp_files()
    if deleted > 0:
        logger.info(f"✓ Cleaned up {deleted} old temporary files")
    
    logger.info(f"✓ Notes directory: {Settings.NOTES_DIR}")
    logger.info(f"✓ Allowed user ID: {Settings.ALLOWED_USER_ID}")
    logger.info("✓ Ready to accept voice messages")


async def shutdown(application: Application):
    """Действия при остановке"""
    logger.info("Shutting down bot...")
    
    # Очистка ресурсов
    await application.shutdown()
    
    logger.info("Bot stopped")


async def main():
    """Главная функция"""
    
    # Настройка логирования
    setup_logging()
    
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Startup
    await startup()
    
    try:
        # Создание приложения
        application = (
            Application.builder()
            .token(Settings.TELEGRAM_BOT_TOKEN)
            .build()
        )
        
        # Регистрация обработчиков
        handlers = BotHandlers()
        handlers.register_handlers(application)
        
        logger.info("Starting bot polling...")
        
        # Запуск бота
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
        logger.info("✓ Bot is running!")
        logger.info("Press Ctrl+C to stop")
        
        # Ожидание завершения
        stop_event = asyncio.Event()
        
        def stop():
            stop_event.set()
        
        # Переопределяем signal handler для asyncio
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop)
        
        await stop_event.wait()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        await shutdown(application)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
