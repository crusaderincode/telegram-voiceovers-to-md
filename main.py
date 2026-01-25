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
from utils import setup_logging


# Обработчики сигналов теперь встроены в основной цикл asyncio


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
    

    
    logger.info(f"✓ Notes directory: {Settings.NOTES_DIR}")
    logger.info(f"✓ Allowed user ID: {Settings.ALLOWED_USER_ID}")
    logger.info("✓ Ready to accept voice messages")


async def shutdown(application: Application):
    """Действия при остановке"""
    logger.info("Shutting down bot...")
    
    # Сначала останавливаем обновление (Updater)
    if application.updater and application.updater.running:
        await application.updater.stop()
    
    # Затем останавливаем само приложение
    if application.running:
        await application.stop()
        
    # Финальная очистка ресурсов
    await application.shutdown()
    
    logger.info("Bot stopped")


async def main():
    """Главная функция"""
    
    # Настройка логирования
    setup_logging()
    
    # Startup
    await startup()
    
    application = None
    
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
        if application:
            await shutdown(application)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
