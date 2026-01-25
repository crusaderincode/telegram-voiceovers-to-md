#!/bin/bash
# Скрипт для запуска бота

set -e

# Активация виртуального окружения
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found. Run ./scripts/setup.sh first"
    exit 1
fi

# Проверка .env
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Copy .env.example and configure it"
    exit 1
fi

# Проверка Ollama сервиса
if ! pgrep -x "ollama" > /dev/null; then
    echo "⚠️  Starting Ollama service..."
    brew services start ollama
    sleep 2
fi

# Запуск бота
echo "🚀 Starting AI Notes Bot..."
python main.py
