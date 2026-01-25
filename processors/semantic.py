"""Semantic processing using Qwen via Ollama/Takopi"""
import json
import re
import subprocess
from typing import Dict, Optional

from loguru import logger

from config.settings import Settings
from config.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, SIMPLE_PROMPT_TEMPLATE


class SemanticProcessor:
    """Семантическая обработка текста через Qwen"""
    
    def __init__(self, model: Optional[str] = None):
        """
        Args:
            model: Название модели (опционально)
        """
        self.model = model or Settings.QWEN_MODEL
        self.temperature = Settings.QWEN_TEMPERATURE
        self.timeout = Settings.QWEN_TIMEOUT
        self.executable = Settings.TAKOPI_EXECUTABLE
        
        self._check_model_available()
    
    def _check_model_available(self):
        """Проверка доступности модели"""
        try:
            result = subprocess.run(
                [self.executable, 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if self.model in result.stdout:
                logger.info(f"Model {self.model} is available")
            else:
                logger.warning(
                    f"Model {self.model} not found. "
                    f"Run: {self.executable} pull {self.model}"
                )
        except Exception as e:
            logger.warning(f"Could not verify model: {e}")
    
    def process(self, transcription: str) -> Dict[str, str]:
        """
        Обработка транскрипции с извлечением структуры
        
        Args:
            transcription: Текст транскрипции
            
        Returns:
            Dict с полями: category, title, content
        """
        try:
            logger.debug(f"Processing transcription ({len(transcription)} chars)")
            
            # Формируем промпт
            user_prompt = USER_PROMPT_TEMPLATE.format(transcription=transcription)
            
            # Запрос к модели
            result = self._run_llm(SYSTEM_PROMPT, user_prompt, format_json=True)
            
            # Парсинг JSON ответа
            response = self._parse_json_response(result)
            
            if response:
                # Валидация категории
                if response['category'] not in Settings.CATEGORIES:
                    logger.warning(f"Invalid category: {response['category']}, using 'инбокс'")
                    response['category'] = 'инбокс'
                
                logger.info(f"Processed: category={response['category']}, title={response['title'][:30]}")
                return response
            else:
                # Fallback если JSON не распарсился
                logger.warning("Failed to parse JSON, using fallback")
                return self._fallback_processing(transcription)
                
        except Exception as e:
            logger.error(f"Semantic processing error: {e}")
            return self._fallback_processing(transcription)
    
    def _run_llm(self, system_prompt: str, user_prompt: str, format_json: bool = False) -> str:
        """
        Запуск LLM через Ollama
        
        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            format_json: Принудительный JSON формат
            
        Returns:
            str: Ответ модели
        """
        cmd = [
            self.executable,
            'run',
            self.model,
        ]
        
        # Формируем полный промпт
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        # Наследуем все переменные окружения и добавляем специфичные для Ollama
        import os
        env = os.environ.copy()
        env['OLLAMA_NUM_GPU'] = '1'
        
        try:
            # Отправляем промпт через stdin
            result = subprocess.run(
                cmd,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env
            )
            
            if result.returncode != 0:
                logger.error(f"LLM error: {result.stderr}")
                raise RuntimeError(f"LLM failed: {result.stderr}")
            
            response = result.stdout.strip()
            
            # Если используется Ollama с JSON mode, можно добавить параметр
            # Но пока возвращаем как есть
            return response
            
        except subprocess.TimeoutExpired:
            logger.error("LLM timeout")
            raise RuntimeError("LLM запрос превысил таймаут")
        except Exception as e:
            logger.error(f"LLM execution error: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, str]]:
        """
        Парсинг JSON ответа от модели
        
        Args:
            response: Ответ модели
            
        Returns:
            Dict или None если не удалось распарсить
        """
        try:
            # Иногда модель добавляет markdown блоки
            # Попробуем извлечь JSON из ```json ... ```
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Пробуем найти просто JSON объект
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response
            
            # Парсинг
            data = json.loads(json_str)
            
            # Валидация структуры
            required_fields = ['category', 'title', 'content']
            if all(field in data for field in required_fields):
                return {
                    'category': str(data['category']).lower(),
                    'title': str(data['title']),
                    'content': str(data['content'])
                }
            else:
                logger.warning(f"Missing required fields in JSON: {data.keys()}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None
    
    def _fallback_processing(self, transcription: str) -> Dict[str, str]:
        """
        Простая обработка без LLM (fallback)
        
        Args:
            transcription: Исходный текст
            
        Returns:
            Dict с базовой структурой
        """
        logger.info("Using fallback processing")
        
        # Простая эвристика для категории
        text_lower = transcription.lower()
        category = 'инбокс'
        
        # Ищем упоминания категорий в начале текста
        first_words = ' '.join(text_lower.split()[:10])
        
        if any(word in first_words for word in ['идея', 'идеи', 'придумал', 'концепция', 'проект']):
            category = 'идеи'
        elif any(word in first_words for word in ['работа', 'задача', 'встреча', 'проект', 'коллега']):
            category = 'работа'
        elif any(word in first_words for word in ['купить', 'жизнь', 'личное', 'дом', 'семья', 'здоровье']):
            category = 'жизнь'
        
        # Простой заголовок из первых слов
        words = transcription.split()[:5]
        title = ' '.join(words)
        if len(title) > 50:
            title = title[:50] + '...'
        
        # Базовое форматирование контента
        content = f"# {title}\n\n{transcription}"
        
        return {
            'category': category,
            'title': title,
            'content': content
        }
    
    def get_simple_title(self, transcription: str) -> str:
        """
        Получить только заголовок (быстрая генерация)
        
        Args:
            transcription: Текст
            
        Returns:
            str: Заголовок
        """
        try:
            prompt = SIMPLE_PROMPT_TEMPLATE.format(transcription=transcription[:500])
            result = self._run_llm("Ты помощник для создания заголовков.", prompt)
            
            # Берем первую строку
            title = result.split('\n')[0].strip()
            # Очищаем от лишних символов
            title = title.strip('*#- "\'')
            
            return title if title else "Заметка"
            
        except Exception as e:
            logger.error(f"Title generation failed: {e}")
            # Fallback - первые слова
            words = transcription.split()[:5]
            return ' '.join(words)
