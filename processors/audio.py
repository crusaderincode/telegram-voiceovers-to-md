"""Audio processing utilities"""
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger
from pydub import AudioSegment

from config.settings import Settings


class AudioProcessor:
    """Обработка аудио файлов"""
    
    @staticmethod
    def convert_to_wav(input_path: Path, output_path: Optional[Path] = None) -> Path:
        """
        Конвертация аудио в WAV формат для whisper.cpp
        
        Args:
            input_path: Путь к входному файлу
            output_path: Путь к выходному файлу (опционально)
            
        Returns:
            Path: Путь к сконвертированному WAV файлу
        """
        if output_path is None:
            output_path = input_path.with_suffix('.wav')
        
        try:
            logger.debug(f"Converting {input_path} to WAV format")
            
            # Используем FFmpeg через pydub для конвертации
            audio = AudioSegment.from_file(str(input_path))
            
            # Whisper требует 16kHz, mono, 16-bit PCM
            audio = audio.set_frame_rate(16000)
            audio = audio.set_channels(1)
            audio = audio.set_sample_width(2)  # 16-bit
            
            # Экспорт
            audio.export(
                str(output_path),
                format='wav',
                parameters=['-ar', '16000', '-ac', '1']
            )
            
            logger.info(f"Audio converted: {output_path.name} ({output_path.stat().st_size / 1024:.1f}KB)")
            return output_path
            
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise RuntimeError(f"Не удалось конвертировать аудио: {e}")
    
    @staticmethod
    def get_audio_duration(file_path: Path) -> float:
        """
        Получение длительности аудио файла
        
        Args:
            file_path: Путь к аудио файлу
            
        Returns:
            float: Длительность в секундах
        """
        try:
            audio = AudioSegment.from_file(str(file_path))
            return len(audio) / 1000.0  # milliseconds to seconds
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    @staticmethod
    def validate_audio_file(file_path: Path, max_duration: int = None) -> tuple[bool, str]:
        """
        Валидация аудио файла
        
        Args:
            file_path: Путь к файлу
            max_duration: Максимальная длительность в секундах
            
        Returns:
            tuple[bool, str]: (валидный, сообщение об ошибке)
        """
        if max_duration is None:
            max_duration = Settings.MAX_VOICE_DURATION
        
        # Проверка существования
        if not file_path.exists():
            return False, "Файл не найден"
        
        # Проверка размера
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > Settings.MAX_FILE_SIZE_MB:
            return False, f"Файл слишком большой: {file_size_mb:.1f}MB"
        
        # Проверка длительности
        try:
            duration = AudioProcessor.get_audio_duration(file_path)
            if duration > max_duration:
                return False, f"Аудио слишком длинное: {duration:.0f}с (макс: {max_duration}с)"
            
            if duration < 1:
                return False, "Аудио слишком короткое"
                
        except Exception as e:
            return False, f"Не удалось прочитать аудио: {e}"
        
        return True, "OK"
