"""Speech-to-Text using whisper.cpp"""
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import Settings


class WhisperTranscriber:
    """Транскрибация аудио в текст через whisper.cpp"""
    
    def __init__(self, model_path: Optional[Path] = None):
        """
        Args:
            model_path: Путь к модели whisper (опционально)
        """
        self.model_path = model_path or Settings.WHISPER_MODEL_PATH
        self.language = Settings.WHISPER_LANGUAGE
        self.threads = Settings.WHISPER_THREADS
        
        # Проверка наличия executable
        self._check_whisper_available()
    
    def _check_whisper_available(self):
        """Проверка доступности whisper.cpp"""
        try:
            # Пробуем найти whisper executable
            # Возможные варианты: whisper-cpp, main, ./whisper.cpp/main
            executables = ['whisper-cpp', 'main', './whisper.cpp/main']
            
            for exe in executables:
                try:
                    result = subprocess.run(
                        [exe, '--help'],
                        capture_output=True,
                        timeout=5
                    )
                    if result.returncode == 0 or 'usage' in result.stderr.decode().lower():
                        self.executable = exe
                        logger.info(f"Found whisper executable: {exe}")
                        return
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            
            # Если ничего не нашли, используем значение из настроек
            self.executable = Settings.WHISPER_EXECUTABLE
            logger.warning(f"Whisper executable not verified, using: {self.executable}")
            
        except Exception as e:
            logger.warning(f"Could not verify whisper: {e}")
            self.executable = Settings.WHISPER_EXECUTABLE
    
    def transcribe(self, audio_path: Path, output_txt: Optional[Path] = None) -> str:
        """
        Транскрибация аудио файла
        
        Args:
            audio_path: Путь к WAV файлу
            output_txt: Путь для сохранения текста (опционально)
            
        Returns:
            str: Распознанный текст
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Whisper model not found: {self.model_path}\n"
                f"Скачайте модель: cd models/whisper && "
                f"bash <(curl -s https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/models/download-ggml-model.sh) large-v3"
            )
        
        try:
            logger.debug(f"Transcribing {audio_path.name}...")
            
            # Временный файл для вывода
            if output_txt is None:
                output_txt = Settings.TRANSCRIPTIONS_DIR / f"{audio_path.stem}.txt"
            
            # Команда для whisper.cpp
            cmd = [
                self.executable,
                '-m', str(self.model_path),
                '-f', str(audio_path),
                '-l', self.language,
                '-t', str(self.threads),
                '--output-txt',
                '--output-file', str(output_txt.with_suffix('')),  # whisper добавит .txt сам
                '--no-timestamps'
            ]
            
            # Запуск whisper
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 минут максимум
            )
            
            if result.returncode != 0:
                logger.error(f"Whisper failed: {result.stderr}")
                raise RuntimeError(f"Whisper error: {result.stderr}")
            
            # Чтение результата
            if output_txt.exists():
                transcription = output_txt.read_text(encoding='utf-8').strip()
            else:
                # Иногда whisper выводит в stdout
                transcription = result.stdout.strip()
            
            logger.info(f"Transcription completed: {len(transcription)} chars")
            return transcription
            
        except subprocess.TimeoutExpired:
            logger.error("Whisper transcription timeout")
            raise RuntimeError("Транскрибация заняла слишком много времени")
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Ошибка транскрибации: {e}")
    
    def transcribe_simple(self, audio_path: Path) -> str:
        """
        Упрощенная версия транскрибации (без сохранения в файл)
        
        Args:
            audio_path: Путь к WAV файлу
            
        Returns:
            str: Распознанный текст
        """
        try:
            cmd = [
                self.executable,
                '-m', str(self.model_path),
                '-f', str(audio_path),
                '-l', self.language,
                '-t', str(self.threads),
                '--no-timestamps',
                '--print-colors'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Парсим вывод (whisper выводит текст в stdout/stderr)
            output = result.stdout + result.stderr
            
            # Ищем строки с транскрипцией (обычно после "[00:00:00.000 --> ...]")
            lines = output.split('\n')
            transcription_lines = []
            
            for line in lines:
                # Пропускаем строки с метаданными
                if any(skip in line.lower() for skip in ['whisper', 'processing', 'load', 'model']):
                    continue
                # Убираем временные метки если есть
                if '-->' in line:
                    continue
                if line.strip():
                    transcription_lines.append(line.strip())
            
            transcription = ' '.join(transcription_lines)
            return transcription.strip()
            
        except Exception as e:
            logger.error(f"Simple transcription failed: {e}")
            return ""
