"""Telegram bot handlers"""
import tempfile
from datetime import datetime
from pathlib import Path

import re
from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ContextTypes,
    filters,
    ConversationHandler
)
from telegram import ReplyKeyboardMarkup

from config.settings import Settings
from processors import (
    AudioProcessor,
    WhisperTranscriber,
    SemanticProcessor,
    TranscriptionValidator,
    OllamaEmbeddings
)
from storage import FileManager, VectorStore
from utils import check_resources
from .auth import authorized_filter, is_authorized_update


class BotHandlers:
    """Обработчики команд и сообщений Telegram бота"""
    
    # Состояния для разговора
    WAITING_CATEGORY_NAME = 1
    
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.transcriber = WhisperTranscriber()
        self.semantic_processor = SemanticProcessor()
        self.file_manager = FileManager()
        self.validator = TranscriptionValidator()
        self.embeddings = OllamaEmbeddings()
        self.vector_store = VectorStore()
        
        # Initialize vector collection
        self.vector_store.init_collection()
    
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
            "   - **'Перескажи'** ... - сделать конспект (по умолчанию)\n"
            "3. Я обработаю аудио и сохраню заметку\n\n"
            "🔍 **Поиск голосом:**\n"
            "Скажите **'Найди ...'** или **'Где ...'**, чтобы получить ответ на вопрос по вашим заметкам.\n\n"
            "📚 **Доступные команды:**\n"
            "/start - Справка\n"
            "/add\_category <имя> - Создать новую категорию\n"
            "/categories - Список категорий\n"
            "/stats - Статистика заметок\n"
            "/search <запрос> - Поиск по заметкам\n"
            "/health - Проверка системы\n\n"
            "🎙️ Отправьте голосовое сообщение для начала!"
        )
        
        keyboard = [
            ['🔍 Поиск'],
            ['📊 Статистика', '📂 Категории'],
            ['➕ Добавить категорию', '💚 Состояние']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)
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
            
            # Проверка на режим "Найди" / "Поиск"
            lower_trans = transcription.lower().strip()
            if lower_trans.startswith(('найди', 'найти', 'поиск', 'ищи', 'где', 'расскажи')):
                await status_msg.edit_text("🔍 Ищу ответ в заметках...")
                
                # Извлекаем запрос и очищаем от мусора
                # 1. Удаляем триггер-слова
                query = re.sub(r'^(найди|найти|поиск|ищи|где|расскажи)', '', transcription, flags=re.IGNORECASE).strip()
                
                # 2. Удаляем вводные слова ("информацию про", "пожалуйста", "все о" и т.д.)
                # Повторяем несколько раз, так как порядок может быть разным (найди пожалуйста информацию про...)
                clean_patterns = [
                    r'^(пожалуйста|мне|нам|быстро|срочно)\s*',
                    r'^(информацию|данные|заметки|заметку|все|всё|что-нибудь|что-то|ответ)\s*', 
                    r'^(про|о|об|на тему|касательно)\s*',
                    r'^(то,?|том,?)\s*',
                    r'^(как|где|что)\s+(?=работает|находится|лежит|это)' # Оставляем "как" если это часть вопроса "как работают...", но удаляем если просто связка. Хотя "как работают" это сам вопрос. Не будем удалять вопросительные слова.
                ]
                
                for pattern in clean_patterns:
                    query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
                
                if not query:
                    await status_msg.edit_text("❓ Вы сказали 'Найди', но не уточнили что именно.")
                    return

                logger.info(f"Cleaned search query: '{query}'")

                # 1. Получаем эмбеддинг запроса
                query_embedding = await self.embeddings.get_embedding(query)
                
                if not query_embedding:
                    await status_msg.edit_text("❌ Ошибка при поиске (Embeddings failed)")
                    return
                
                # 2. Ищем релевантные заметки (Повышаем порог до 0.55)
                results = self.vector_store.search(query_vector=query_embedding, limit=10, score_threshold=0.55)
                
                # Логируем результаты для отладки
                if results:
                    for i, hit in enumerate(results):
                        logger.info(f"Search hit {i}: score={hit.score}, title={hit.payload.get('title')}, path={hit.payload.get('path')}")
                
                if not results:
                     await status_msg.edit_text(f"🔍 По запросу '{query}' ничего не найдено (score < 0.55).")
                     return
                
                # 3. Группируем результаты по файлам и берем только топ-2 уникальных источника
                unique_results = {}
                for hit in results:
                    path_str = hit.payload.get('path')
                    if path_str and path_str not in unique_results:
                        unique_results[path_str] = hit
                        if len(unique_results) >= 2:
                            break
                
                # 4. Формируем контекст для LLM из уникальных источников
                context_docs = []
                sources_paths = []
                
                for path_str, hit in unique_results.items():
                    doc = {
                        'title': hit.payload.get('title'),
                        'content': hit.payload.get('content', '')
                    }
                    
                    # Читаем контент файла
                    path_obj = Path(path_str)
                    if path_obj.exists():
                        try:
                            content = path_obj.read_text(encoding='utf-8')
                            doc['content'] = content
                            context_docs.append(doc)
                            sources_paths.append(path_obj)
                        except Exception as e:
                            logger.error(f"Failed to read file {path_str}: {e}")

                if not context_docs:
                    await status_msg.edit_text("❌ Не удалось прочитать найденные файлы.")
                    return
                
                # 5. Генерация ответа
                answer = self.semantic_processor.generate_answer_from_context(query, context_docs)
                
                final_response = f"🤖 **Ответ:**\n{answer}\n\n📂 Файлы с источниками ниже:"
                await status_msg.edit_text(final_response, parse_mode='Markdown')
                
                # Отправка самих файлов
                if sources_paths:
                    for path in sources_paths[:5]: # Ограничение 5 файлов чтоб не спамить
                        try:
                            await update.message.reply_document(document=path)
                        except Exception as e:
                            logger.error(f"Failed to send file {path}: {e}")
                
                # Удаляем аудио, так как это был поисковый запрос
                try:
                    temp_ogg.unlink()
                    wav_path.unlink()
                except:
                    pass
                return

            # 4. Семантическая обработка (обычный режим заметки)
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
            
            # 7. Индексация для поиска
            try:
                # Combine title and content for better context
                full_text = f"{processed['title']}\n\n{processed['content']}"
                embedding = await self.embeddings.get_embedding(full_text)
                
                if embedding:
                    self.vector_store.add_note(
                        note_id=str(file_path),
                        vector=embedding,
                        payload={
                            "category": processed['category'],
                            "title": processed['title'],
                            "created_at": timestamp.isoformat(),
                            "path": str(file_path)
                        }
                    )
                    logger.info(f"Note indexed for search: {file_path.name}")
                else:
                    logger.warning(f"Failed to generate embedding for {file_path.name}")
            except Exception as e:
                logger.error(f"Indexing failed for {file_path.name}: {e}")
            
            
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
        """Команда /search и кнопка Поиск"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return
        
        # Если команда вызвана без аргументов или кнопкой
        if not context.args and update.message.text == '🔍 Поиск':
            await update.message.reply_text("🔎 Отправьте текст для поиска...")
            return

        query = ' '.join(context.args) if context.args else update.message.text
        
        # Игнорируем саму команду /search в тексте если она есть
        if query.startswith('/search'):
            query = query[7:].strip()
            
        if not query:
            await update.message.reply_text("🔎 Введите поисковый запрос после команды /search")
            return

        await update.message.reply_text(f"🔎 Ищу: '{query}'...")
        
        # Генерируем embedding запроса
        query_embedding = await self.embeddings.get_embedding(query)
        
        if not query_embedding:
            await update.message.reply_text("❌ Не удалось обработать запрос (ошибка Embeddings)")
            return
            
        # Поиск в векторной базе (Используем новый порог)
        results = self.vector_store.search(query_vector=query_embedding, limit=10, score_threshold=0.55)
        
        # Фильтруем уникальные пути
        unique_hits = []
        seen_paths = set()
        for hit in results:
            path = hit.payload.get('path')
            if path and path not in seen_paths:
                seen_paths.add(path)
                unique_hits.append(hit)
                if len(unique_hits) >= 2: # Максимум 2 источника
                    break

        if not unique_hits:
            await update.message.reply_text(f"🔍 По запросу '{query}' ничего не найдено (score < 0.55)")
            return
        
        message = f"🔍 **Результаты поиска (топ-{len(unique_hits)}):**\n\n"
        
        for i, hit in enumerate(unique_hits, 1):
            score = hit.score
            payload = hit.payload
            title = payload.get('title', 'Без названия')
            category = payload.get('category', 'инбокс')
            path_str = payload.get('path', '')
            
            # Получаем имя файла из пути
            filename = Path(path_str).name if path_str else '???'
            
            emoji = Settings.CATEGORY_EMOJI.get(category, '📝')
            message += f"{i}. {emoji} **{title}** ({score:.2f})\n   `{filename}`\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Semantic search: '{query}' - {len(results)} results")
    

    
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

    async def start_add_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса добавления категории"""
        if not is_authorized_update(update):
            await update.message.reply_text("❌ Доступ запрещен")
            return ConversationHandler.END
            
        await update.message.reply_text(
            "✍️ Введите название для новой категории:",
            parse_mode='Markdown'
        )
        return self.WAITING_CATEGORY_NAME

    async def handle_new_category_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия категории"""
        if not is_authorized_update(update):
            return ConversationHandler.END
            
        category_name = update.message.text.strip()
        
        # Проверка на отмену
        if category_name.lower() == 'отмена':
            await update.message.reply_text("❌ Создание категории отменено")
            return ConversationHandler.END
        
        if self.file_manager.create_category(category_name):
            await update.message.reply_text(f"✅ Категория '{category_name}' создана!")
        else:
            await update.message.reply_text(
                f"❌ Не удалось создать категорию '{category_name}'.\n"
                "Возможно такое имя недопустимо или категория уже существует."
            )
            
        return ConversationHandler.END

    async def cancel_add_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена добавления категории"""
        await update.message.reply_text("❌ Операция отменена")
        return ConversationHandler.END

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
        
        # Conversation Handler для добавления категории (Регистрируем первым!)
        add_category_handler = ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.Regex('^➕ Добавить категорию$') & authorized_filter,
                    self.start_add_category
                )
            ],
            states={
                self.WAITING_CATEGORY_NAME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & authorized_filter,
                        self.handle_new_category_name
                    )
                ]
            },
            fallbacks=[
                CommandHandler('cancel', self.cancel_add_category, filters=authorized_filter),
                MessageHandler(filters.COMMAND & authorized_filter, self.cancel_add_category)
            ]
        )
        application.add_handler(add_category_handler)
        
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
        
        # Кнопки меню
        application.add_handler(
            MessageHandler(
                filters.Regex('^📊 Статистика$') & authorized_filter,
                self.stats
            )
        )
        application.add_handler(
                MessageHandler(
                    filters.Regex('^🔍 Поиск$') & authorized_filter,
                    self.search
                )
            )
        application.add_handler(
            MessageHandler(
                filters.Regex('^📂 Категории$') & authorized_filter,
                self.list_categories
            )
        )
        

        application.add_handler(
            MessageHandler(
                filters.Regex('^💚 Состояние$') & authorized_filter,
                self.health
            )
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
        
        # Обработчик текстовых сообщений (если не команда) - можно использовать для поиска
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & authorized_filter,
                self.search
            )
        )
        
        logger.info("All handlers registered")

    async def shutdown(self):
        """Cleanup resources"""
        if self.embeddings:
            await self.embeddings.close()
        if self.vector_store:
            self.vector_store.close()
