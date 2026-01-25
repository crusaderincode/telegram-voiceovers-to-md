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
