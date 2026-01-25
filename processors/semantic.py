"""Semantic processing using Qwen via Ollama/Takopi"""
import json
import re
import subprocess
from typing import Dict, Optional, List

from loguru import logger

from config.settings import Settings
from config.prompts import SYSTEM_PROMPT_REMEMBER, SYSTEM_PROMPT_RECORD, USER_PROMPT_TEMPLATE, SIMPLE_PROMPT_TEMPLATE


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
    
    def process(self, transcription: str, available_categories: List[str] = None) -> Dict[str, str]:
        """
        Обработка транскрипции с извлечением структуры
        
        Args:
            transcription: Текст транскрипции
            
        Returns:
            Dict с полями: category, title, content
        """
        try:
            logger.debug(f"Processing transcription ({len(transcription)} chars)")
            
            if not available_categories:
                available_categories = ['инбокс']
            
            # Определение режима и промпта
            mode = 'remember' # Default
            clean_transcription = transcription.strip()
            
            # Проверяем команды в начале
            lower_trans = clean_transcription.lower()
            if lower_trans.startswith(('запиши', 'записать')):
                mode = 'record'
                # Убираем команду из начала
                clean_transcription = re.sub(r'^(запиши|записать)\s*[.,!-]?\s*', '', clean_transcription, flags=re.IGNORECASE)
            elif lower_trans.startswith(('запомни', 'запомнить')):
                mode = 'remember'
                # Убираем команду из начала
                clean_transcription = re.sub(r'^(запомни|запомнить)\s*[.,!-]?\s*', '', clean_transcription, flags=re.IGNORECASE)
            
            base_system_prompt = SYSTEM_PROMPT_RECORD if mode == 'record' else SYSTEM_PROMPT_REMEMBER
            
            # Формируем список категорий для промпта
            categories_str = '\n'.join([f'- "{cat}"' for cat in available_categories])
            system_prompt = base_system_prompt.format(categories=categories_str)
            
            logger.info(f"Using mode: {mode} for transcription")

            # Формируем промпт
            user_prompt = USER_PROMPT_TEMPLATE.format(transcription=clean_transcription)
            
            # Запрос к модели
            result = self._run_llm(system_prompt, user_prompt, format_json=True)
            
            # Парсинг JSON ответа
            response = self._parse_json_response(result)
            
            if response:
                # Валидация категории
                if response['category'] not in available_categories:
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
                content = self._clean_content(str(data['content']))
                title = str(data['title']).strip()
                
                return {
                    'category': str(data['category']).lower(),
                    'title': title,
                    'content': content
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

    def _clean_content(self, content: str) -> str:
        """
        Очистка содержимого от артефактов LLM
        
        Args:
            content: Исходный текст контента
            
        Returns:
            str: Очищенный текст
        """
        # 1. Убираем "разговорные" префиксы
        prefixes_to_remove = [
            r'^пересказ(у|жу)?\s*заметки:\s*',
            r'^вот\s*пересказ:\s*',
            r'^вот\s*текст:\s*',
            r'^заметка:\s*',
            r'^текст:\s*',
            r'^контент:\s*',
            r'^обработанный\s*текст:\s*'
        ]
        
        for p in prefixes_to_remove:
            content = re.sub(p, '', content, flags=re.IGNORECASE | re.MULTILINE).strip()
            
        # 2. Убираем утечки системного промпта в конце (иногда модель дописывает инструкции)
        # Ищем фразы типа "Верни ТОЛЬКО JSON..." или "Ответ должен быть..." в конце текста
        prompt_leaks = [
            r'верни\s+только\s+json.*$',
            r'ответ\s+должен\s+быть.*$',
            r'никаких\s+дополнительных\s+комментариев.*$',
            r'не\s+добавляй\s+никаких.*$'
        ]
        
        for p in prompt_leaks:
            content = re.sub(p, '', content, flags=re.IGNORECASE | re.DOTALL).strip()

        return content
    
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
        
        if any(word in first_words for word in ['работа', 'задача', 'встреча', 'проект']):
            category = 'работа'
        elif any(word in first_words for word in ['идея', 'идеи', 'придумал']):
            category = 'идеи'
        
        # Если такой категории нет, то инбокс
        # (в fallback логике мы не знаем доступные категории точно, но если мы сюда упали, 
        # значит LLM сломалась. Вернем инбокс или то что наэвристили если повезет)
        # Для безопасности лучше вернуть инбокс, но оставим эвристику как hint
        
        
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
