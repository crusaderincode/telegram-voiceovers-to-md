# AI Notes Bot 🎙️ → 📝

Telegram-бот для автоматического создания структурированных markdown-заметок из голосовых сообщений с использованием локальных AI моделей.

## ✨ Особенности

- 🔒 **Полностью локальная обработка** - никаких облачных API
- 🚀 **Оптимизация под Apple M1** - использует Core ML и Metal
- 🎯 **Умная категоризация** - автоматическое определение или ручное создание
- 📝 **Два режима записи** - "Запиши" (дословно) или "Перескажи" (конспект)
- ⌨️ **Удобное меню** - быстрый доступ к функциям через кнопки
- 💾 **Файловая организация** - каждая категория в отдельной папке

## 🛠 Технологии

- **Speech-to-Text**: [whisper.cpp](https://github.com/ggml-org/whisper.cpp) (модель large-v3)
- **LLM**: [Qwen 2.5:3b](https://ollama.com/library/qwen2.5) через Ollama
- **Bot Framework**: python-telegram-bot
- **Audio Processing**: pydub + FFmpeg

## 📋 Требования

- macOS (оптимизировано для M1/M2)
- Python 3.10+
- 8GB+ RAM
- ~5GB свободного места на диске (для моделей)

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
cd ~/projects
git clone <your-repo-url> ai-notes
cd ai-notes
```

### 2. Запуск установки

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

Скрипт автоматически:
- Установит Homebrew (если нужно)
- Установит FFmpeg и Ollama
- Создаст виртуальное окружение Python
- Загрузит модели Whisper и Qwen
- Соберет whisper.cpp с поддержкой Core ML
- Создаст структуру директорий

### 3. Настройка Telegram бота

1. Создайте бота через [@BotFather](https://t.me/botfather):
   - Отправьте `/newbot`
   - Следуйте инструкциям
   - Скопируйте токен бота

2. Получите свой User ID через [@userinfobot](https://t.me/userinfobot)

3. Отредактируйте `.env`:

```bash
nano .env
```

Заполните:
```env
TELEGRAM_BOT_TOKEN=your_token_here
ALLOWED_USER_ID=your_user_id_here
```

### 4. Запуск бота

```bash
source venv/bin/activate
python main.py
```

При успешном запуске вы увидите:
```
✓ Configuration validated
✓ Ready to accept voice messages
✓ Bot is running!
```

## 📱 Использование

### Создание заметки

1. Откройте диалог с ботом в Telegram
2. Запишите голосовое сообщение
3. **Выберите режим (опционально)**:
   - "Запиши..." - для дословного сохранения текста.
   - "Перескажи..." или просто текст - для создания структурированного конспекта (по умолчанию).
4. Получите структурированную заметку!

**Пример (Пересказ):**
> 🎙️ "Перескажи. Нужно созвониться с командой по поводу нового проекта завтра в 10 утра. Обсудить архитектуру и сроки."

**Пример (Запись):**
> 🎙️ "Запиши. Мой номер телефона 8-900-123-45-67, позвони мне когда освободишься."

**Результат:**
```markdown
---
created: 2024-01-25T14:30:00+03:00
category: работа
---

# Созвон с командой по новому проекту

Необходимо провести встречу завтра в 10:00.

**Повестка:**
- Архитектура проекта
- Обсуждение сроков
```

### Доступные команды

| Команда | Описание |
|---------|----------|
| `/start` | Справка и клавиатура меню |
| `/add_category <имя>` | Создать новую категорию |
| `/categories` | Список всех категорий |
| `/stats` | Статистика по заметкам |
| `/search <запрос>` | Поиск по содержимому |
| `/health` | Проверка состояния системы |
| `/cleanup` | Очистка временных файлов |

## 📁 Структура проекта

```
ai-notes/
├── bot/                    # Telegram bot handlers
├── processors/             # Audio, STT, LLM processing
├── storage/                # File management
├── config/                 # Settings and prompts
├── utils/                  # Logging, resources
├── data/                   # Temporary files
│   ├── audio/
│   ├── transcriptions/
│   └── logs/
├── notes/                  # Your notes!
│   ├── идеи/
│   ├── жизнь/
│   ├── работа/
│   └── инбокс/
├── models/                 # AI models
│   └── whisper/
├── whisper.cpp/            # Whisper binary
├── main.py                 # Entry point
├── requirements.txt
└── .env                    # Configuration
```

## ⚙️ Конфигурация

Все настройки находятся в `.env`:

```env
# Базовые
TELEGRAM_BOT_TOKEN=...
ALLOWED_USER_ID=...

# Пути
WHISPER_MODEL_PATH=./models/whisper/ggml-large-v3.bin
NOTES_DIR=./notes

# Whisper (STT)
WHISPER_LANGUAGE=ru
WHISPER_THREADS=4

# Qwen (LLM)
QWEN_MODEL=qwen2.5:3b
QWEN_TEMPERATURE=0.3
QWEN_TIMEOUT=30

# Ограничения
MAX_VOICE_DURATION=180      # 3 минуты
MAX_FILE_SIZE_MB=10

# Логирование
LOG_LEVEL=INFO
```

## 🔧 Производительность

На MacBook Air M1:

| Действие | Время |
|----------|-------|
| Скачивание аудио | 0.5-2 сек |
| Конвертация в WAV | 0.1-0.5 сек |
| Транскрибация (30 сек) | 3-8 сек |
| LLM обработка | 2-5 сек |
| **Итого (30 сек аудио)** | **6-16 сек** |

## 🐛 Troubleshooting

### Whisper не найден

```bash
# Проверьте сборку
cd whisper.cpp
WHISPER_COREML=1 make -j

# Обновите путь в .env
WHISPER_EXECUTABLE=./whisper.cpp/main
```

### Модель Qwen не загружена

```bash
# Загрузите заново
ollama pull qwen2.5:3b

# Проверьте список
ollama list
```

### Бот не отвечает

```bash
# Проверьте логи
tail -f data/logs/bot_*.log

# Проверьте токен
python -c "from config.settings import Settings; print(Settings.TELEGRAM_BOT_TOKEN)"
```

### Ошибка памяти

Уменьшите размер модели Whisper в `.env`:
```env
WHISPER_MODEL_PATH=./models/whisper/ggml-medium.bin
```

Или используйте меньшую модель Qwen:
```bash
ollama pull qwen2.5:1.5b
```

## 🚀 Автозапуск (macOS launchd)

Создайте `~/Library/LaunchAgents/com.user.ai-notes-bot.plist`:

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
        <string>/Users/YOUR_USERNAME/projects/ai-notes/venv/bin/python</string>
        <string>/Users/YOUR_USERNAME/projects/ai-notes/main.py</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/projects/ai-notes</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/projects/ai-notes/data/logs/stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/projects/ai-notes/data/logs/stderr.log</string>
</dict>
</plist>
```

Затем:
```bash
launchctl load ~/Library/LaunchAgents/com.user.ai-notes-bot.plist
launchctl start com.user.ai-notes-bot
```

## 📊 Мониторинг

### Просмотр логов

```bash
# Основной лог
tail -f data/logs/bot_$(date +%Y-%m-%d).log

# Только ошибки
tail -f data/logs/errors_$(date +%Y-%m-%d).log
```

### Статистика через бота

Отправьте `/stats` в Telegram для получения сводки по заметкам.

### Системные ресурсы

Отправьте `/health` для проверки памяти и диска.

## 🗺 Roadmap

- [ ] Веб-интерфейс для просмотра заметок
- [ ] Полнотекстовый поиск (MeiliSearch)
- [ ] Теги и связи между заметками
- [ ] Автоматическая генерация саммари
- [ ] RAG для ответов на вопросы по заметкам
- [ ] Поддержка фото и документов

## 🤝 Contributing

Буду рад вашим предложениям! Открывайте issues и pull requests.

## 📄 Лицензия

MIT

## 🙏 Благодарности

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) - оптимизированный STT
- [Ollama](https://ollama.com) - простой запуск LLM
- [Qwen](https://github.com/QwenLM/Qwen2.5) - качественная языковая модель
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - отличный framework

---

Сделано с ❤️ для локальной приватной обработки заметок
