"""Telegram bot handlers"""
import tempfile
from datetime import datetime
from pathlib import Path

from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config.settings import Settings
from processors import (
    AudioProcessor,
    WhisperTranscriber,
    SemanticProcessor,
    TranscriptionValidator
)
from storage import FileManager
from utils import check_resources
from .auth import authorized_filter, is_authorized_update


class BotHandlers:
    """Обработчики команд и сообщений Telegram бота"""
    
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.transcriber = WhisperTranscriber()
        self.semantic_processor = SemanticProcessor()
        self.file_manager = FileManager()
        self.validator = TranscriptionValidator()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        welcome_message = (
            "👋 Привет! Я бот для создания заметок из голосовых сообщений.\n\n"
            "📝 **Как использовать:**\n"
            "1. Запишите голосовое сообщение\n"
            "2. В начале сообщения можно сказать тип обработки:\n"
            "   - **'Запиши'** ... - записать дословно\n"
            "   - **'Запомни'** ... - сделать конспект (по умолчанию)\n"
            "3. Я обработаю аудио и сохраню заметку\n\n"
            "📚 **Доступные команды:**\n"
            "/start - Справка\n"
            "/add\_category <имя> - Создать новую категорию\n"
            "/categories - Список категорий\n"
            "/stats - Статистика заметок\n"
            "/search <запрос> - Поиск по заметкам\n"
            "/health - Проверка системы\n\n"
            "🎙️ Отправьте голосовое сообщение для начала!"
        )
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        logger.info(f"User {update.effective_user.id} started the bot")
    
    async def process_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка голосового сообщения"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        voice = update.message.voice
        user_id = update.effective_user.id
        
        logger.info(f"Received voice from user {user_id}: {voice.duration}s")
        
        # Проверка длительности
        if voice.duration > Settings.MAX_VOICE_DURATION:
            await update.message.reply_text(
                f"❌ Голосовое сообщение слишком длинное ({voice.duration}с)\n"
                f"Максимум: {Settings.MAX_VOICE_DURATION}с"
            )
            return
        
        # Проверка ресурсов
        resources_ok, resource_msg = check_resources()
        if not resources_ok:
            await update.message.reply_text(f"⚠️ {resource_msg}")
            return
        
        try:
            # 1. Скачивание аудио
            status_msg = await update.message.reply_text("⏳ Скачиваю аудио...")
            
            voice_file = await voice.get_file()
            timestamp = datetime.now()
            temp_ogg = Settings.AUDIO_DIR / f"voice_{timestamp.strftime('%Y%m%d_%H%M%S')}.ogg"
            
            await voice_file.download_to_drive(temp_ogg)
            logger.debug(f"Downloaded to {temp_ogg}")
            
            # 2. Конвертация в WAV
            await status_msg.edit_text("🎵 Конвертирую аудио...")
            wav_path = self.audio_processor.convert_to_wav(temp_ogg)
            
            # Валидация аудио
            is_valid, validation_msg = self.audio_processor.validate_audio_file(wav_path)
            if not is_valid:
                await status_msg.edit_text(f"❌ {validation_msg}")
                return
            
            # 3. Транскрибация
            await status_msg.edit_text("🎤 Распознаю речь...")
            transcription = self.transcriber.transcribe(wav_path)
            
            # Валидация транскрипции
            is_valid, validation_msg = self.validator.validate(transcription)
            if not is_valid:
                await status_msg.edit_text(
                    f"❌ Ошибка распознавания: {validation_msg}\n"
                    f"Попробуйте записать заново."
                )
                logger.warning(f"Invalid transcription: {validation_msg}")
                return
            
            # Очистка транскрипции
            transcription = self.validator.clean_transcription(transcription)
            logger.debug(f"Transcription: {transcription[:100]}...")
            
            # 4. Семантическая обработка
            await status_msg.edit_text("🤖 Обрабатываю текст...")
            
            # Получаем актуальные категории
            categories = self.file_manager.get_categories()
            
            processed = self.semantic_processor.process(transcription, available_categories=categories)
            
            # 5. Сохранение заметки
            file_path = self.file_manager.save_note(
                category=processed['category'],
                title=processed['title'],
                content=processed['content'],
                timestamp=timestamp
            )
            
            # 6. Отправка результата
            emoji = Settings.CATEGORY_EMOJI.get(processed['category'], '📝')
            
            success_message = (
                f"{emoji} **Заметка сохранена!**\n\n"
                f"📂 Категория: `{processed['category']}`\n"
                f"📄 Заголовок: {processed['title']}\n"
                f"📁 Файл: `{file_path.name}`\n\n"
                f"✅ Готово!"
            )
            
            await status_msg.edit_text(success_message, parse_mode='Markdown')
            logger.info(f"Note saved successfully: {file_path}")
            
            # Опционально: удаление временных файлов
            try:
                temp_ogg.unlink()
                wav_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
        
        except Exception as e:
            logger.error(f"Error processing voice: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Произошла ошибка при обработке:\n{str(e)}\n\n"
                f"Попробуйте еще раз или обратитесь к администратору."
            )
    
    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats - статистика заметок"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        stats = self.file_manager.get_stats()
        
        message = "📊 **Статистика заметок**\n\n"
        
        categories = self.file_manager.get_categories()
        
        for category in categories:
            emoji = Settings.CATEGORY_EMOJI.get(category, '📁')
            count = stats.get(category, 0)
            message += f"{emoji} {category.capitalize()}: {count}\n"
        
        message += f"\n**Всего: {stats['total']}**"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info("Stats requested")
    
    async def search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /search - поиск по заметкам"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Использование: /search <запрос>\n"
                "Пример: /search важная встреча"
            )
            return
        
        query = ' '.join(context.args)
        results = self.file_manager.search_notes(query)
        
        if not results:
            await update.message.reply_text(f"🔍 По запросу '{query}' ничего не найдено")
            return
        
        message = f"🔍 Найдено заметок: {len(results)}\n\n"
        
        for i, file_path in enumerate(results[:10], 1):
            category = file_path.parent.name
            emoji = Settings.CATEGORY_EMOJI.get(category, '📝')
            message += f"{i}. {emoji} `{file_path.name}`\n"
        
        if len(results) > 10:
            message += f"\n... и ещё {len(results) - 10}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Search: '{query}' - {len(results)} results")
    

    
    async def add_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add_category - добавить категорию"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Использование: /add_category <имя>\n"
                "Пример: /add_category путешествия"
            )
            return
        
        category_name = context.args[0]
        
        if self.file_manager.create_category(category_name):
            await update.message.reply_text(f"✅ Категория '{category_name}' создана!")
        else:
            await update.message.reply_text(f"❌ Не удалось создать категорию '{category_name}'")

    async def list_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /categories - список категорий"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        categories = self.file_manager.get_categories()
        
        if not categories:
            await update.message.reply_text("📂 Категорий пока нет")
            return
        
        message = "📂 **Доступные категории:**\n\n"
        for category in categories:
            emoji = Settings.CATEGORY_EMOJI.get(category, '📁')
            message += f"{emoji} `{category}`\n"
            
        await update.message.reply_text(message, parse_mode='Markdown')
    async def health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /health - проверка системы"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        from utils.resources import get_disk_usage_info, get_memory_usage_info
        
        # Проверка ресурсов
        resources_ok, resource_msg = check_resources()
        
        # Статистика
        stats = self.file_manager.get_stats()
        
        message = (
            "💚 **Статус системы**\n\n"
            f"{get_memory_usage_info()}\n"
            f"{get_disk_usage_info()}\n\n"
            f"📝 Всего заметок: {stats['total']}\n"
            f"Status: {'✅ OK' if resources_ok else '⚠️ ' + resource_msg}"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Глобальный обработчик ошибок"""
        logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла внутренняя ошибка.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
    
    def register_handlers(self, application: Application):
        """Регистрация всех обработчиков"""
        
        # Команды
        application.add_handler(
            CommandHandler('start', self.start, filters=authorized_filter)
        )
        application.add_handler(
            CommandHandler('add_category', self.add_category, filters=authorized_filter)
        )
        application.add_handler(
            CommandHandler('categories', self.list_categories, filters=authorized_filter)
        )
        application.add_handler(
            CommandHandler('stats', self.stats, filters=authorized_filter)
        )
        application.add_handler(
            CommandHandler('search', self.search, filters=authorized_filter)
        )

        application.add_handler(
            CommandHandler('health', self.health, filters=authorized_filter)
        )
        
        # Голосовые сообщения
        application.add_handler(
            MessageHandler(
                filters.VOICE & authorized_filter,
                self.process_voice
            )
        )
        
        # Обработчик ошибок
        application.add_error_handler(self.error_handler)
        
        logger.info("All handlers registered")
