"""System resources monitoring and cleanup"""
import gc
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

import psutil
from loguru import logger

from config.settings import Settings


def check_resources() -> Tuple[bool, str]:
    """
    Проверка доступных системных ресурсов
    
    Returns:
        Tuple[bool, str]: (успешно, сообщение)
    """
    try:
        # Проверка памяти
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            gc.collect()  # Принудительная сборка мусора
            memory = psutil.virtual_memory()  # Повторная проверка
            
            if memory.percent > 90:
                return False, f"Недостаточно памяти: {memory.percent}% использовано"
        
        # Проверка диска
        disk = psutil.disk_usage(str(Settings.BASE_DIR))
        if disk.percent > 90:
            return False, f"Диск почти заполнен: {disk.percent}% использовано"
        
        logger.debug(f"Resources OK: Memory {memory.percent}%, Disk {disk.percent}%")
        return True, "OK"
        
    except Exception as e:
        logger.error(f"Error checking resources: {e}")
        return True, f"Не удалось проверить ресурсы: {e}"


def cleanup_temp_files(older_than_hours: int = None) -> int:
    """
    Очистка временных файлов старше определённого времени
    
    Args:
        older_than_hours: Количество часов. По умолчанию из настроек
        
    Returns:
        int: Количество удалённых файлов
    """
    if older_than_hours is None:
        older_than_hours = Settings.CLEANUP_TEMP_FILES_HOURS
    
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    deleted_count = 0
    
    # Очистка аудио файлов
    for audio_file in Settings.AUDIO_DIR.glob('*'):
        if audio_file.is_file():
            file_time = datetime.fromtimestamp(audio_file.stat().st_mtime)
            if file_time < cutoff:
                try:
                    audio_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old audio: {audio_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {audio_file}: {e}")
    
    # Очистка транскрипций
    for trans_file in Settings.TRANSCRIPTIONS_DIR.glob('*'):
        if trans_file.is_file():
            file_time = datetime.fromtimestamp(trans_file.stat().st_mtime)
            if file_time < cutoff:
                try:
                    trans_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old transcription: {trans_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {trans_file}: {e}")
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} temporary files")
    
    return deleted_count


def get_disk_usage_info() -> str:
    """Получить информацию об использовании диска"""
    disk = psutil.disk_usage(str(Settings.BASE_DIR))
    total_gb = disk.total / (1024**3)
    used_gb = disk.used / (1024**3)
    free_gb = disk.free / (1024**3)
    
    return (
        f"💾 Диск: {used_gb:.1f}GB / {total_gb:.1f}GB ({disk.percent}%)\n"
        f"Свободно: {free_gb:.1f}GB"
    )


def get_memory_usage_info() -> str:
    """Получить информацию об использовании памяти"""
    memory = psutil.virtual_memory()
    total_gb = memory.total / (1024**3)
    used_gb = memory.used / (1024**3)
    
    return (
        f"🧠 Память: {used_gb:.1f}GB / {total_gb:.1f}GB ({memory.percent}%)"
    )
