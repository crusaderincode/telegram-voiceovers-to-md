"""File management for notes"""
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import Settings


class FileManager:
    """Управление файлами заметок"""
    
    def __init__(self, notes_dir: Optional[Path] = None):
        """
        Args:
            notes_dir: Корневая директория для заметок
        """
        self.notes_dir = notes_dir or Settings.NOTES_DIR
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Создание необходимых директорий"""
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        
        for category in Settings.CATEGORIES:
            category_dir = self.notes_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def sanitize_title(title: str, max_length: int = 50) -> str:
        """
        Очистка заголовка для имени файла
        
        Args:
            title: Исходный заголовок
            max_length: Максимальная длина
            
        Returns:
            str: Очищенный заголовок
        """
        # Приводим к lowercase
        clean = title.lower()
        
        # Удаляем все кроме букв, цифр, пробелов и дефисов
        clean = re.sub(r'[^\w\s-]', '', clean)
        
        # Заменяем пробелы на подчеркивания
        clean = re.sub(r'[\s_]+', '_', clean)
        
        # Убираем дефисы в начале/конце
        clean = clean.strip('-_')
        
        # Ограничиваем длину
        if len(clean) > max_length:
            clean = clean[:max_length].rstrip('_-')
        
        # Если после очистки ничего не осталось
        if not clean:
            clean = 'заметка'
        
        return clean
    
    def generate_filename(
        self, 
        title: str, 
        timestamp: Optional[datetime] = None,
        extension: str = 'md'
    ) -> str:
        """
        Генерация имени файла
        
        Args:
            title: Заголовок заметки
            timestamp: Временная метка (по умолчанию - сейчас)
            extension: Расширение файла
            
        Returns:
            str: Имя файла
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        clean_title = self.sanitize_title(title)
        time_str = timestamp.strftime("%Y-%m-%d_%H%M%S")
        
        return f"{clean_title}_{time_str}.{extension}"
    
    def save_note(
        self,
        category: str,
        title: str,
        content: str,
        timestamp: Optional[datetime] = None
    ) -> Path:
        """
        Сохранение заметки
        
        Args:
            category: Категория заметки
            title: Заголовок
            content: Содержимое в markdown
            timestamp: Временная метка
            
        Returns:
            Path: Путь к сохраненному файлу
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Валидация категории
        if category not in Settings.CATEGORIES:
            logger.warning(f"Invalid category '{category}', using 'инбокс'")
            category = 'инбокс'
        
        category_dir = self.notes_dir / category
        
        # Генерация уникального имени файла
        counter = 0
        while True:
            filename = self.generate_filename(title, timestamp)
            
            if counter > 0:
                # Добавляем счетчик если файл уже существует
                name_parts = filename.rsplit('.', 1)
                filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
            
            file_path = category_dir / filename
            
            if not file_path.exists():
                break
            
            counter += 1
            
            if counter > 100:
                raise RuntimeError("Не удалось создать уникальное имя файла")
        
        # Формирование контента с метаданными
        full_content = self._format_note(title, content, category, timestamp)
        
        try:
            # Сохранение файла
            file_path.write_text(full_content, encoding='utf-8')
            logger.info(f"Note saved: {file_path}")
            return file_path
            
        except PermissionError:
            logger.error(f"Permission denied: {file_path}")
            raise RuntimeError("Нет прав на запись в директорию")
        except OSError as e:
            if e.errno == 28:  # ENOSPC - No space left on device
                logger.error("Disk full")
                raise RuntimeError("Диск переполнен")
            raise RuntimeError(f"Ошибка записи файла: {e}")
    
    def _format_note(
        self,
        title: str,
        content: str,
        category: str,
        timestamp: datetime
    ) -> str:
        """
        Форматирование заметки с YAML frontmatter
        
        Args:
            title: Заголовок
            content: Содержимое
            category: Категория
            timestamp: Временная метка
            
        Returns:
            str: Отформатированная заметка
        """
        # YAML frontmatter
        frontmatter = (
            f"---\n"
            f"created: {timestamp.isoformat()}\n"
            f"category: {category}\n"
            f"title: {title}\n"
            f"---\n\n"
        )
        
        # Если контент не начинается с заголовка, добавляем
        if not content.startswith('#'):
            content = f"# {title}\n\n{content}"
        
        return frontmatter + content
    
    def get_notes_count(self, category: Optional[str] = None) -> int:
        """
        Получить количество заметок
        
        Args:
            category: Категория (если None - все категории)
            
        Returns:
            int: Количество заметок
        """
        if category:
            category_dir = self.notes_dir / category
            if category_dir.exists():
                return len(list(category_dir.glob('*.md')))
            return 0
        else:
            # Все заметки
            total = 0
            for cat in Settings.CATEGORIES:
                total += self.get_notes_count(cat)
            return total
    
    def get_stats(self) -> dict:
        """
        Получить статистику по заметкам
        
        Returns:
            dict: Статистика по категориям
        """
        stats = {}
        for category in Settings.CATEGORIES:
            stats[category] = self.get_notes_count(category)
        stats['total'] = sum(stats.values())
        return stats
    
    def search_notes(self, query: str, category: Optional[str] = None) -> list[Path]:
        """
        Поиск заметок по содержимому
        
        Args:
            query: Поисковый запрос
            category: Категория для поиска (если None - во всех)
            
        Returns:
            list[Path]: Найденные файлы
        """
        query = query.lower()
        results = []
        
        categories = [category] if category else Settings.CATEGORIES
        
        for cat in categories:
            category_dir = self.notes_dir / cat
            if not category_dir.exists():
                continue
            
            for md_file in category_dir.glob('*.md'):
                try:
                    content = md_file.read_text(encoding='utf-8').lower()
                    if query in content:
                        results.append(md_file)
                except Exception as e:
                    logger.warning(f"Error reading {md_file}: {e}")
        
        return results
    

