"""Application settings"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()


class Settings:
    """Централизованные настройки приложения"""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    ALLOWED_USER_ID: int = int(os.getenv('ALLOWED_USER_ID', '0'))
    
    # Пути
    BASE_DIR: Path = Path(__file__).parent.parent
    WHISPER_MODEL_PATH: Path = Path(os.getenv('WHISPER_MODEL_PATH', './models/whisper/ggml-large-v3.bin'))
    NOTES_DIR: Path = Path(os.getenv('NOTES_DIR', './notes'))
    TEMP_DIR: Path = Path(os.getenv('TEMP_DIR', './data'))
    
    # Производные пути
    AUDIO_DIR: Path = TEMP_DIR / 'audio'
    TRANSCRIPTIONS_DIR: Path = TEMP_DIR / 'transcriptions'
    LOGS_DIR: Path = TEMP_DIR / 'logs'
    
    # Whisper
    WHISPER_LANGUAGE: str = os.getenv('WHISPER_LANGUAGE', 'ru')
    WHISPER_THREADS: int = int(os.getenv('WHISPER_THREADS', '4'))
    WHISPER_EXECUTABLE: str = os.getenv('WHISPER_EXECUTABLE', 'whisper-cpp')
    
    # Qwen
    QWEN_MODEL: str = os.getenv('QWEN_MODEL', 'qwen2.5:3b')
    QWEN_TEMPERATURE: float = float(os.getenv('QWEN_TEMPERATURE', '0.3'))
    QWEN_TIMEOUT: int = int(os.getenv('QWEN_TIMEOUT', '30'))
    TAKOPI_EXECUTABLE: str = os.getenv('TAKOPI_EXECUTABLE', 'ollama')
    
    # Ограничения
    MAX_VOICE_DURATION: int = int(os.getenv('MAX_VOICE_DURATION', '180'))
    MAX_FILE_SIZE_MB: int = int(os.getenv('MAX_FILE_SIZE_MB', '10'))
    
    # Логирование
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Очистка
    CLEANUP_TEMP_FILES_HOURS: int = int(os.getenv('CLEANUP_TEMP_FILES_HOURS', '24'))

    # Embeddings (Ollama)
    OLLAMA_BASE_URL: str = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_EMBEDDING_MODEL: str = os.getenv('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')
    
    # Vector Store (Qdrant)
    # Используем локальный путь для Qdrant (embedded mode) по умолчанию
    QDRANT_PATH: Path = Path(os.getenv('QDRANT_PATH', './data/qdrant_db'))
    QDRANT_COLLECTION_NAME: str = os.getenv('QDRANT_COLLECTION_NAME', 'notes')
    QDRANT_SCORE_THRESHOLD: float = float(os.getenv('QDRANT_SCORE_THRESHOLD', '0.55'))
    
    # Категории

    CATEGORY_EMOJI = {
        'идеи': '💡',
        'жизнь': '🌱',
        'работа': '💼',
        'инбокс': '📥'
    }
    
    @classmethod
    def validate(cls) -> bool:
        """Проверка критичных настроек"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен")
        
        if cls.ALLOWED_USER_ID == 0:
            raise ValueError("ALLOWED_USER_ID не установлен")
        
        # Создание необходимых директорий
        for directory in [cls.AUDIO_DIR, cls.TRANSCRIPTIONS_DIR, cls.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        

        
        return True


# Валидация при импорте
Settings.validate()
