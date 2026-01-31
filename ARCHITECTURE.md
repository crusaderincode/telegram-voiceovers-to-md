# Архитектура локального Telegram-бота для AI-заметок

## Обзор системы

Система представляет собой пайплайн обработки голосовых сообщений из Telegram с полностью локальным выполнением на MacBook Air M1.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌────────────┐
│  Telegram   │────▶│   Bot API    │────▶│ whisper.cpp │────▶│  Qwen2.5:3b  │────▶│ FileSystem │
│  (voice)    │     │  (download)  │     │   (STT)     │     │  (semantic)  │     │   (.md)    │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └────────────┘
       │                   │                    │                     │                    │
       ▼                   ▼                    ▼                     ▼                    ▼
   Buttons Menu      audio.ogg        transcription.txt      structured.md        categories/
   (Categories,     (conversion)       (record / sum)        (JSON parsing)       ├─ [динамические]
    Search,                                                       │               └─ инбокс/
     Stats)                                                       ▼
                                                             Vector Store
                                                            (Qdrant Local)
                                                                  ▲
                                                                  │
                                                            Embedding Model
                                                           (nomic-embed-text)
```
```

---

## 1. Архитектура компонентов

### 1.1 Telegram Bot Handler
**Назначение:** Прием и первичная обработка голосовых сообщений

**Технологии:**
- Python 3.10+ с библиотекой `python-telegram-bot` (asyncio-based)
- Whitelist пользователя (Telegram User ID)

**Ответственность:**
- Проверка авторизации пользователя
- Скачивание голосового файла (.ogg)
- Конвертация в формат, поддерживаемый whisper.cpp (.wav 16kHz mono)
- Передача управления следующему компоненту
- Отправка статусов пользователю ("Обрабатываю...", "Готово!")

**Входные данные:**
- Telegram voice message (`.ogg` формат)

**Выходные данные:**
- Локальный аудио-файл `audio/{timestamp}.wav`

---

### 1.2 Speech-to-Text (whisper.cpp)
**Назначение:** Транскрибация аудио в текст

**Технологии:**
- whisper.cpp (Core ML оптимизация для M1)
- Модель: `ggml-medium.bin` или `ggml-large-v3.bin` (для лучшего русского)

**Установка и оптимизация:**
```bash
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
make clean
WHISPER_COREML=1 make -j  # Core ML для M1
./models/download-ggml-model.sh large-v3
```

**Запуск:**
```bash
./main -m models/ggml-large-v3.bin \
       -f audio.wav \
       -l ru \
       -t 4 \
       --output-txt \
       --no-timestamps
```

**Параметры оптимизации:**
- `-t 4` — использовать 4 потока (M1 имеет 4 производительных ядра)
- `--no-timestamps` — убирает временные метки из текста
- `-l ru` — язык распознавания

**Входные данные:**
- `audio/{timestamp}.wav`

**Выходные данные:**
- `transcriptions/{timestamp}.txt` — сырой текст транскрипции

---

### 1.3 Semantic Processor (Qwen2.5:3b через takopi)
**Назначение:** Структурирование текста, определение категории, генерация заголовка

**Технологии:**
- takopi (https://github.com/banteg/takopi)
- Модель: `qwen2.5:3b` (оптимизирована под M1)

**Установка takopi:**
```bash
brew install takopi
# или
pip install takopi
```

**Загрузка модели Qwen:**
```bash
takopi pull qwen2.5:3b
```

**Промпт для обработки (см. раздел 3)**

**Входные данные:**
- Сырой текст транскрипции
- Список доступных категорий из FileSystem

**Выходные данные:**
- JSON с полями:
  - `category` — категория (одна из существующих или инбокс)
  - `title` — заголовок заметки
  - `content` — отформатированный markdown (дословно или конспект)

**Режимы обработки:**
- **Summarize (default)**: Очистка от слов-паразитов, структурирование, конспект.
- **Record**: Точная запись без сокращений, только форматирование.

---

### 1.5 Semantic Search Engine
**Назначение:** Поиск заметок по смыслу

**Технологии:**
- **Embeddings**: `nomic-embed-text` (через Ollama)
- **Vector DB**: Qdrant (Embedded mode, локальное хранилище в `./data/qdrant_db`)

**Процесс:**
1. При сохранении заметки генерируется вектор (embedding) из заголовка и текста.
2. Вектор + метаданные сохраняются в Qdrant.
3. При поиске запрос также превращается в вектор.
4. Выполняется Cosine Similarity поиск ближайших векторов.

---

### 1.4 File Manager
**Назначение:** Сохранение структурированных заметок

**Структура директорий:**
```
~/notes/
├─ идеи/
│  └─ ai_заметки_2024-03-21_143055.md
├─ жизнь/
│  └─ покупки_продукты_2024-03-21_120330.md
├─ работа/
│  └─ встреча_команда_2024-03-21_093012.md
└─ инбокс/
   └─ разное_2024-03-21_183245.md
```

**Логика именования:**
```python
import re
from datetime import datetime

def sanitize_title(title: str) -> str:
    """Очистка заголовка для имени файла"""
    # Удаляем спецсимволы, оставляем буквы, цифры, пробелы
    clean = re.sub(r'[^\w\s-]', '', title.lower())
    # Заменяем пробелы на подчеркивания
    clean = re.sub(r'[\s_]+', '_', clean)
    return clean[:50]  # Максимум 50 символов

def generate_filename(title: str, timestamp: datetime) -> str:
    clean_title = sanitize_title(title)
    time_str = timestamp.strftime("%Y-%m-%d_%H%M%S")
    return f"{clean_title}_{time_str}.md"
```

**Формат markdown-файла:**
```markdown
---
created: 2024-03-21T14:30:55+03:00
category: идеи
---

# {Заголовок}

{Структурированный контент}
```

---

## 2. Поток данных (Data Flow)

### Детальный пайплайн

```python
# Псевдокод общего потока

async def process_voice_message(update, context):
    """Главный обработчик голосовых сообщений"""
    
    # 1. Валидация пользователя
    if not is_authorized_user(update.effective_user.id):
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    # 2. Скачивание аудио
    await update.message.reply_text("⏳ Скачиваю аудио...")
    voice_file = await download_voice(update.message.voice)
    
    # 3. Конвертация в WAV
    wav_path = convert_to_wav(voice_file)
    
    # 4. Транскрибация
    await update.message.reply_text("🎤 Распознаю речь...")
    transcription = await transcribe_audio(wav_path)
    
    if not transcription or len(transcription.strip()) < 10:
        await update.message.reply_text("❌ Не удалось распознать речь")
        return
    
    # 5. Семантическая обработка
    await update.message.reply_text("🤖 Обрабатываю текст...")
    processed = await semantic_process(transcription)
    
    # 6. Сохранение
    file_path = save_note(...)
    
    # 7. Индексация (Асинхронно)
    embedding = get_embedding(processed['title'] + processed['content'])
    save_to_qdrant(embedding, metadata)
    
    # 8. Подтверждение
    category_emoji = {
        'идеи': '💡',
        'жизнь': '🌱',
        'работа': '💼',
        'инбокс': '📥'
    }
    
    emoji = category_emoji.get(processed['category'], '📝')
    await update.message.reply_text(
        f"{emoji} Сохранено в **{processed['category']}**\n"
        f"📄 {processed['title']}\n"
        f"📁 `{file_path}`"
    )
```

### Временные характеристики

| Этап | Время (примерно) | Комментарий |
|------|------------------|-------------|
| Скачивание аудио | 0.5-2 сек | Зависит от размера файла |
| Конвертация в WAV | 0.1-0.5 сек | FFmpeg быстрый |
| Транскрибация (30 сек аудио) | 3-8 сек | whisper.cpp на M1 |
| LLM обработка | 2-5 сек | Qwen2.5:3b локально |
| Сохранение файла | <0.1 сек | I/O операция |
| **Общее время** | **6-16 сек** | Для 30-секундного сообщения |

---

## 3. Промпт для Qwen2.5

### Системные промпты

#### 1. Режим Пересказа (Summarize)
```python
SYSTEM_PROMPT_SUMMARIZE = """Ты — ассистент для обработки голосовых заметок. Твоя задача:
1. Определить категорию заметки из текста (по ключевым словам)
2. Убрать слова-паразиты (ну, вот, типа, короче, э-э-э, м-м-м)
3. Структурировать текст в markdown с заголовками, списками, абзацами
4. Создать краткий заголовок (2-5 слов)

Доступные категории:
{categories}

Ответ строго в JSON:
{
  "category": "одна из доступных категорий",
  "title": "Краткий заголовок",
  "content": "Отформатированный markdown текст"
}
"""
```

#### 2. Режим Записи (Record)
```python
SYSTEM_PROMPT_RECORD = """Ты — ассистент для точной записи голосовых заметок. Твоя задача:
1. Определить категорию из текста
2. Сохранить текст максимально близко к оригиналу (дословно)
3. Применить markdown форматирование
4. Создать краткий заголовок

Ответ строго в JSON.
"""
```

### Обработка команд в тексте
Система ищет ключевые слова в начале транскрипции:
- "Запиши", "Записать" -> Режим **Record**
- "Перескажи", "Запомни" -> Режим **Summarize**

### Запуск через takopi

```python
import subprocess
import json

def semantic_process(transcription: str) -> dict:
    """Обработка текста через Qwen2.5"""
    
    prompt = USER_PROMPT_TEMPLATE.format(transcription=transcription)
    
    # Запуск takopi
    result = subprocess.run(
        [
            'takopi', 'run', 'qwen2.5:3b',
            '--system', SYSTEM_PROMPT,
            '--prompt', prompt,
            '--temperature', '0.3',  # Низкая температура для консистентности
            '--top-p', '0.9',
            '--format', 'json'  # Принудительный JSON
        ],
        capture_output=True,
        text=True,
        timeout=30
    )
    
    try:
        response = json.loads(result.stdout)
        
        # Валидация категории
        if response['category'] not in ['идеи', 'жизнь', 'работа', 'инбокс']:
            response['category'] = 'инбокс'
        
        return response
        
    except (json.JSONDecodeError, KeyError) as e:
        # Fallback если модель не вернула валидный JSON
        return {
            'category': 'инбокс',
            'title': 'Заметка',
            'content': transcription
        }
```

---

## 4. Edge Cases и обработка ошибок

### 4.1 Плохое качество речи

**Проблема:** Whisper вернул пустую строку или мусор

**Решение:**
```python
def validate_transcription(text: str) -> tuple[bool, str]:
    """Проверка качества транскрипции"""
    
    # Минимальная длина
    if len(text.strip()) < 10:
        return False, "Слишком короткий текст"
    
    # Проверка на мусорные символы (>50% не буквы/цифры)
    alpha_ratio = sum(c.isalnum() or c.isspace() for c in text) / len(text)
    if alpha_ratio < 0.5:
        return False, "Слишком много мусорных символов"
    
    # Проверка на повторяющиеся паттерны (whisper иногда зацикливается)
    words = text.split()
    if len(words) > 10:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.3:
            return False, "Обнаружены повторения"
    
    return True, "OK"

# Использование:
is_valid, reason = validate_transcription(transcription)
if not is_valid:
    await update.message.reply_text(
        f"❌ Ошибка распознавания: {reason}\n"
        "Попробуйте записать заново."
    )
    # Сохраняем оригинальное аудио для ручной проверки
    save_failed_audio(wav_path, reason)
    return
```

### 4.2 Неясная категория

**Проблема:** Модель не может определить категорию или пользователь не назвал её

**Решение:**
- По умолчанию сохранять в `инбокс`
- Добавить команду `/move` для ручного перемещения:

```python
async def move_note(update, context):
    """
    Команда: /move <filename> <категория>
    Пример: /move заметка_2024-03-21_143055 идеи
    """
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "Использование: /move <имя_файла> <категория>"
        )
        return
    
    filename, new_category = args
    # Логика перемещения между папками
    # ...
```

### 4.3 Длинные сообщения

**Проблема:** Сообщения >2 минут могут быть слишком большими

**Решение:**
```python
MAX_VOICE_DURATION = 180  # 3 минуты

async def process_voice_message(update, context):
    voice = update.message.voice
    
    if voice.duration > MAX_VOICE_DURATION:
        await update.message.reply_text(
            f"❌ Сообщение слишком длинное ({voice.duration}с)\n"
            f"Максимум: {MAX_VOICE_DURATION}с\n"
            "Разбейте на несколько частей."
        )
        return
```

### 4.4 Ошибки файловой системы

**Проблема:** Нет прав, диск заполнен, конфликт имен

**Решение:**
```python
import os
from pathlib import Path

def save_note(category: str, title: str, content: str) -> str:
    """Безопасное сохранение с обработкой ошибок"""
    
    base_dir = Path.home() / "notes"
    category_dir = base_dir / category
    
    try:
        # Создаем директорию если не существует
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем уникальное имя
        timestamp = datetime.now()
        counter = 0
        while True:
            filename = generate_filename(title, timestamp)
            if counter > 0:
                filename = filename.replace('.md', f'_{counter}.md')
            
            file_path = category_dir / filename
            if not file_path.exists():
                break
            counter += 1
        
        # Записываем файл
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"---\n")
            f.write(f"created: {timestamp.isoformat()}\n")
            f.write(f"category: {category}\n")
            f.write(f"---\n\n")
            f.write(content)
        
        return str(file_path)
        
    except PermissionError:
        raise Exception("Нет прав на запись в директорию")
    except OSError as e:
        if e.errno == 28:  # No space left
            raise Exception("Диск переполнен")
        raise
```

### 4.5 Сбои LLM

**Проблема:** Qwen не запустился или вернул невалидный ответ

**Решение:**
```python
def semantic_process_with_fallback(transcription: str) -> dict:
    """Обработка с откатом на простой режим"""
    
    try:
        return semantic_process(transcription)
    except Exception as e:
        # Логируем ошибку
        logger.error(f"LLM failed: {e}")
        
        # Простая эвристика для категории
        text_lower = transcription.lower()
        category = 'инбокс'
        
        if any(word in text_lower[:50] for word in ['идея', 'придумал', 'концепция']):
            category = 'идеи'
        elif any(word in text_lower[:50] for word in ['работа', 'задача', 'проект', 'встреча']):
            category = 'работа'
        elif any(word in text_lower[:50] for word in ['купить', 'жизнь', 'личное']):
            category = 'жизнь'
        
        # Простой заголовок из первых слов
        words = transcription.split()[:5]
        title = ' '.join(words)
        
        return {
            'category': category,
            'title': title,
            'content': transcription  # Без обработки
        }
```

---

## 5. Оптимизация под M1

### 5.1 whisper.cpp

**Core ML бэкенд:**
```bash
# При компиляции
WHISPER_COREML=1 make -j

# Конвертация модели в Core ML
./models/generate-coreml-model.sh large-v3
```

**Преимущества:**
- Использование Neural Engine на M1
- Ускорение в 2-3 раза по сравнению с CPU
- Меньшее энергопотребление

### 5.2 takopi / Ollama

**Metal бэкенд для Qwen:**
- takopi автоматически использует Metal на M1
- Убедитесь что `GGML_METAL=1` при установке

**Настройки производительности:**
```bash
# Проверка Metal
takopi run qwen2.5:3b --verbose

# Оптимальные параметры для M1
takopi run qwen2.5:3b \
  --num-gpu 1 \        # Использовать GPU
  --num-thread 4 \     # 4 потока для CPU
  --batch-size 512     # Размер батча
```

### 5.3 Конвертация аудио (FFmpeg)

```bash
# Установка с аппаратным ускорением
brew install ffmpeg

# Конвертация с оптимизацией
ffmpeg -i input.ogg \
       -ar 16000 \           # 16kHz
       -ac 1 \               # Моно
       -c:a pcm_s16le \      # 16-bit PCM
       -threads 4 \          # 4 потока
       output.wav
```

### 5.4 Управление памятью

```python
import psutil
import gc

def check_resources():
    """Проверка доступных ресурсов"""
    
    # Память
    memory = psutil.virtual_memory()
    if memory.percent > 85:
        gc.collect()  # Принудительная очистка
        raise Exception("Недостаточно памяти")
    
    # Место на диске
    disk = psutil.disk_usage('/')
    if disk.percent > 90:
        raise Exception("Диск почти заполнен")
    
    return True
```

### 5.5 Оптимизация поиска
- Используется легковесная модель `nomic-embed-text` (быстрая генерация)
- Qdrant в режиме Embedded не требует отдельного процесса/контейнера
- Индексы сохраняются на диске, потребление RAM минимально (~50-100MB для тысяч заметок)

---

## 6. Технический стек

### 6.1 Основные зависимости

**Python (requirements.txt):**
```txt
# Telegram
python-telegram-bot==20.7
python-telegram-bot[job-queue]==20.7

# Аудио обработка
pydub==0.25.1
soundfile==0.12.1

# Системные утилиты
psutil==5.9.6
python-dotenv==1.0.0

# Логирование
loguru==0.7.2
```

**Системные зависимости:**
```bash
brew install ffmpeg
brew install whisper.cpp  # или компиляция из исходников
brew install ollama
```
```

### 6.2 Структура проекта

```
ai-notes/
├── bot/
│   ├── __init__.py
│   ├── handlers.py          # Telegram обработчики
│   ├── auth.py              # Авторизация пользователя
│   └── notifications.py     # Отправка статусов
├── processors/
│   ├── __init__.py
│   ├── audio.py             # Конвертация аудио
│   ├── transcription.py     # Whisper wrapper
│   ├── semantic.py          # Qwen wrapper
│   └── validator.py         # Валидация данных
├── storage/
│   ├── __init__.py
│   ├── file_manager.py      # Работа с файловой системой
│   └── metadata.py          # Метаданные заметок
├── config/
│   ├── __init__.py
│   ├── settings.py          # Конфигурация
│   └── prompts.py           # LLM промпты
├── utils/
│   ├── __init__.py
│   ├── logging.py           # Настройка логирования
│   └── resources.py         # Мониторинг ресурсов
├── data/
│   ├── audio/               # Временные аудио файлы
│   ├── transcriptions/      # Временные транскрипции
│   ├── qdrant_db/           # Векторная база данных
│   └── logs/                # Логи
├── models/
│   └── whisper/             # Модели whisper
│       └── ggml-large-v3.bin
├── notes/                   # Результаты (заметки)
│   ├── идеи/
│   ├── жизнь/
│   ├── работа/
│   └── инбокс/
├── .env                     # Секреты (Telegram токен)
├── main.py                  # Точка входа
├── requirements.txt
└── README.md
```

---

## 7. Конфигурация (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_ID=123456789  # Ваш Telegram User ID

# Пути
WHISPER_MODEL_PATH=./models/whisper/ggml-large-v3.bin
NOTES_DIR=/Users/yourusername/notes
TEMP_DIR=./data
QDRANT_PATH=./data/qdrant_db

# Embeddings
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Whisper настройки
WHISPER_LANGUAGE=ru
WHISPER_THREADS=4

# Qwen настройки
QWEN_MODEL=qwen2.5:3b
QWEN_TEMPERATURE=0.3
QWEN_TIMEOUT=30

# Ограничения
MAX_VOICE_DURATION=180
MAX_FILE_SIZE_MB=10

# Логирование
LOG_LEVEL=INFO
```

---

## 8. Мониторинг и логирование

### Структура логов

```python
from loguru import logger

# Настройка логирования
logger.add(
    "data/logs/bot_{time:YYYY-MM-DD}.log",
    rotation="00:00",      # Новый файл каждый день
    retention="30 days",   # Хранить 30 дней
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Примеры логирования
logger.info(f"Получено сообщение от {user_id}")
logger.warning(f"Низкое качество транскрипции: {score}")
logger.error(f"Ошибка LLM: {error}")
```

### Метрики для отслеживания

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ProcessingMetrics:
    timestamp: datetime
    user_id: int
    audio_duration: float
    transcription_time: float
    llm_time: float
    total_time: float
    category: str
    success: bool
    error: str = None

# Сохранение метрик в JSON
import json

def save_metrics(metrics: ProcessingMetrics):
    with open('data/logs/metrics.jsonl', 'a') as f:
        f.write(json.dumps(metrics.__dict__, default=str) + '\n')
```

---

## 9. Развертывание и запуск

### 9.1 Первоначальная настройка

```bash
# 1. Клонирование и настройка проекта
git clone <your-repo>
cd ai-notes

# 2. Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Установка системных зависимостей
brew install ffmpeg whisper.cpp takopi

# 5. Загрузка моделей
./scripts/download-models.sh

# 6. Настройка .env
cp .env.example .env
# Отредактировать .env с вашими токенами

# 7. Создание структуры директорий
mkdir -p notes/{идеи,жизнь,работа,инбокс}
mkdir -p data/{audio,transcriptions,logs}
```

### 9.2 Запуск бота

```bash
# Разовый запуск
python main.py

# Запуск в фоне (macOS)
nohup python main.py > data/logs/bot.log 2>&1 &

# Запуск через systemd (если настроен) или launchd
launchctl load ~/Library/LaunchAgents/ai-notes-bot.plist
```

### 9.3 Автозапуск при загрузке (macOS launchd)

Создать файл `~/Library/LaunchAgents/ai-notes-bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" 
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.ai-notes-bot</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/Users/yourusername/ai-notes/venv/bin/python</string>
        <string>/Users/yourusername/ai-notes/main.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/yourusername/ai-notes</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>/Users/yourusername/ai-notes/data/logs/stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/yourusername/ai-notes/data/logs/stderr.log</string>
</dict>
</plist>
```

---

## 10. Дополнительные возможности

### 10.1 Поиск по заметкам

```python
# bot/handlers.py

async def search_notes(update, context):
    """
    Команда: /search <запрос>
    Поиск по содержимому всех заметок
    """
    query = ' '.join(context.args).lower()
    results = []
    
    notes_dir = Path(os.getenv('NOTES_DIR'))
    for md_file in notes_dir.rglob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        if query in content.lower():
            results.append(md_file)
    
    if results:
        message = f"Найдено {len(results)} заметок:\n\n"
        for file in results[:10]:  # Первые 10
            message += f"📄 `{file.name}`\n"
    else:
        message = "Ничего не найдено"
    
    await update.message.reply_text(message)
```

### 10.2 Статистика

```python
async def stats(update, context):
    """
    Команда: /stats
    Показывает динамическую статистику
    """
    categories = file_manager.get_categories()
    stats = file_manager.get_stats()
    
    message = "📊 **Статистика заметок**\n\n"
    for cat in categories:
        count = stats.get(cat, 0)
        message += f"- {cat.capitalize()}: {count}\n"
    
    await update.message.reply_text(message)
```

### 10.3 Экспорт в другие форматы

```python
def export_to_notion_csv():
    """Экспорт всех заметок в CSV для импорта в Notion"""
    # Реализация экспорта
    pass

def export_to_obsidian():
    """Подготовка структуры для Obsidian"""
    # Добавление backlinks, tags
    pass
```

---

## 11. Тестирование

### Unit-тесты (pytest)

```python
# tests/test_validators.py

def test_transcription_validation():
    from processors.validator import validate_transcription
    
    # Валидный текст
    text = "Это нормальный текст заметки о чем-то важном"
    is_valid, reason = validate_transcription(text)
    assert is_valid
    
    # Слишком короткий
    text = "Привет"
    is_valid, reason = validate_transcription(text)
    assert not is_valid
    
    # Мусор
    text = "###@@@%%%***"
    is_valid, reason = validate_transcription(text)
    assert not is_valid
```

### Интеграционные тесты

```python
# tests/test_pipeline.py

async def test_full_pipeline():
    """Тест полного пайплайна с моками"""
    
    # Мокаем Telegram API
    mock_update = create_mock_update(voice_duration=30)
    
    # Прогоняем через пайплайн
    result = await process_voice_message(mock_update, None)
    
    # Проверяем результат
    assert result.success
    assert result.category in ['идеи', 'жизнь', 'работа', 'инбокс']
    assert Path(result.file_path).exists()
```

---

## 12. Безопасность

### 12.1 Авторизация

```python
ALLOWED_USERS = [int(os.getenv('ALLOWED_USER_ID'))]

def is_authorized(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

# Application filter
from telegram.ext import filters

app.add_handler(
    MessageHandler(
        filters.VOICE & filters.User(user_id=ALLOWED_USERS),
        process_voice_message
    )
)
```

### 12.2 Защита данных

- Все данные хранятся локально
- Никаких внешних API
- Логи не содержат персональных данных
- Аудио файлы удаляются после обработки (опционально)

```python
def cleanup_temp_files(older_than_hours=24):
    """Очистка временных файлов старше N часов"""
    temp_dir = Path('./data/audio')
    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    
    for file in temp_dir.iterdir():
        if file.stat().st_mtime < cutoff.timestamp():
            file.unlink()
```

---

## 13. Roadmap улучшений

### Фаза 1 (MVP)
- ✅ Базовый пайплайн
- ✅ 4 категории
- ✅ Сохранение в markdown

### Фаза 2
- 🔲 Веб-интерфейс для просмотра заметок
- 🔲 Полнотекстовый поиск (Elasticsearch / MeiliSearch)
- 🔲 Теги и связи между заметками

### Фаза 3
- 🔲 Автоматическая генерация саммари за день/неделю
- 🔲 Напоминания на основе контента
- 🔲 Интеграция с календарем

### Фаза 4
- 🔲 RAG для ответов на вопросы по заметкам
- 🔲 Мультимодальность (фото, документы)
- 🔲 Синхронизация между устройствами

---

## Заключение

Эта архитектура обеспечивает:

✅ **Полную приватность** — все работает локально  
✅ **Производительность** — оптимизация под M1  
✅ **Надёжность** — обработка ошибок и fallback  
✅ **Расширяемость** — модульная структура  
✅ **Удобство** — простой Telegram-интерфейс  

Система спроектирована с учётом ограничений MacBook Air M1 и может обрабатывать до **10-15 голосовых заметок в день** без проблем с производительностью.

**Следующий шаг:** Реализация компонентов согласно этой архитектуре.
