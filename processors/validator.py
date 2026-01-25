"""Transcription validation"""
from typing import Tuple

from loguru import logger


class TranscriptionValidator:
    """Валидация качества транскрипции"""
    
    @staticmethod
    def validate(text: str, min_length: int = 10) -> Tuple[bool, str]:
        """
        Проверка качества транскрипции
        
        Args:
            text: Текст транскрипции
            min_length: Минимальная длина текста
            
        Returns:
            Tuple[bool, str]: (валидный, причина если невалидный)
        """
        if not text or not text.strip():
            return False, "Пустой текст"
        
        text = text.strip()
        
        # Проверка минимальной длины
        if len(text) < min_length:
            return False, f"Текст слишком короткий ({len(text)} символов)"
        
        # Проверка на мусорные символы
        # Считаем процент букв/цифр/пробелов
        alnum_count = sum(c.isalnum() or c.isspace() or c in '.,!?-—:;()[]"\'«»' for c in text)
        alpha_ratio = alnum_count / len(text) if len(text) > 0 else 0
        
        if alpha_ratio < 0.5:
            return False, f"Слишком много мусорных символов ({alpha_ratio*100:.0f}% валидных)"
        
        # Проверка на повторяющиеся паттерны (whisper иногда зацикливается)
        words = text.split()
        if len(words) > 10:
            unique_words = len(set(words))
            unique_ratio = unique_words / len(words)
            
            if unique_ratio < 0.3:
                return False, f"Обнаружены повторения ({unique_ratio*100:.0f}% уникальных слов)"
        
        # Проверка на слишком длинные "слова" (возможно мусор)
        max_word_length = max(len(word) for word in words) if words else 0
        if max_word_length > 50:
            return False, "Обнаружены подозрительно длинные фрагменты"
        
        logger.debug(f"Transcription validated: {len(text)} chars, {len(words)} words")
        return True, "OK"
    
    @staticmethod
    def clean_transcription(text: str) -> str:
        """
        Базовая очистка транскрипции
        
        Args:
            text: Исходный текст
            
        Returns:
            str: Очищенный текст
        """
        # Удаляем лишние пробелы
        text = ' '.join(text.split())
        
        # Удаляем повторяющиеся знаки препинания
        import re
        text = re.sub(r'([.,!?])\1+', r'\1', text)
        
        # Капитализация начала предложений
        sentences = text.split('. ')
        sentences = [s.strip().capitalize() for s in sentences if s.strip()]
        text = '. '.join(sentences)
        
        return text.strip()
