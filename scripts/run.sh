#!/bin/bash
# Скрипт для запуска бота

set -e

# Определение корневой директории проекта (на уровень выше директории скрипта)
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

# Активация виртуального окружения
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found in $PROJECT_ROOT. Run ./scripts/setup.sh first"
    exit 1
fi

# Проверка .env
if [ ! -f ".env" ]; then
    echo "❌ .env file not found in $PROJECT_ROOT. Copy .env.example and configure it"
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
