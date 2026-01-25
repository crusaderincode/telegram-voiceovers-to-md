# Быстрая установка AI Notes Bot

## 1️⃣ Установка зависимостей

```bash
./scripts/setup.sh
```

Скрипт установит все необходимое (займет ~10-15 минут):
- Homebrew, FFmpeg, Ollama
- Python виртуальное окружение
- AI модели (Whisper large-v3, Qwen 2.5:3b)
- whisper.cpp с оптимизацией для M1

## 2️⃣ Настройка Telegram

### Создание бота
1. Откройте [@BotFather](https://t.me/botfather)
2. Отправьте `/newbot`
3. Введите имя: `My AI Notes Bot`
4. Введите username: `myainotes_bot` (должен быть уникальным)
5. **Скопируйте токен** (выглядит как `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Получение User ID
1. Откройте [@userinfobot](https://t.me/userinfobot)
2. Отправьте `/start`
3. **Скопируйте ваш ID** (число, например `987654321`)

### Заполнение .env
```bash
nano .env
```

Замените:
```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
ALLOWED_USER_ID=ваш_user_id
```

Сохраните: `Ctrl+O`, `Enter`, `Ctrl+X`

## 3️⃣ Проверка установки

```bash
./scripts/check_status.sh
```

Должны быть все ✓ галочки.

## 4️⃣ Запуск бота

```bash
./scripts/run.sh
```

Или вручную:
```bash
source venv/bin/activate
python main.py
```

## 5️⃣ Первое использование

1. Найдите вашего бота в Telegram
2. Отправьте `/start` — появится клавиатура с кнопками
3. Запишите голосовое сообщение:
   - "Перескажи... (или без команды) — для умного конспекта
   - "Запиши..." — для дословной расшифровки
4. Дождитесь обработки (6-15 сек)
5. Ваша заметка будет автоматически сохранена в нужную категорию в папке `notes/`

## 📋 Полезные команды

```bash
# Проверка статуса
./scripts/check_status.sh

# Просмотр логов
tail -f data/logs/bot_*.log

# Тест компонентов
python test_components.py

# Остановка бота
Ctrl+C (в терминале где запущен бот)
```

## ⚠️ Возможные проблемы

### "TELEGRAM_BOT_TOKEN не установлен"
→ Отредактируйте `.env`, добавьте токен от BotFather

### "Whisper model not found"
→ Запустите: `./scripts/setup.sh` повторно

### "Ollama service not running"
→ Запустите: `brew services start ollama`

### Бот не отвечает
→ Проверьте что ваш User ID правильный в `.env`

## 📚 Дополнительная информация

Полная документация: [README.md](README.md)

Архитектура проекта: [ARCHITECTURE.md](ARCHITECTURE.md)

---

**Готово! 🎉**

Теперь отправьте боту голосовое сообщение и получите структурированную заметку!
