#!/bin/bash
# Скрипт установки зависимостей для AI Notes Bot

set -e

echo "================================"
echo "AI Notes Bot - Setup Script"
echo "================================"
echo ""

# Определение корневой директории проекта
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"
echo "📍 Project root: $PROJECT_ROOT"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка ОС
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}❌ This script is designed for macOS${NC}"
    exit 1
fi

echo -e "${GREEN}✓ macOS detected${NC}"

# 1. Проверка Homebrew
echo ""
echo "1️⃣  Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}⚠️  Homebrew not found. Installing...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo -e "${GREEN}✓ Homebrew is installed${NC}"
fi

# 2. Установка системных зависимостей
echo ""
echo "2️⃣  Installing system dependencies..."

# FFmpeg для аудио конвертации
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing FFmpeg..."
    brew install ffmpeg
else
    echo -e "${GREEN}✓ FFmpeg already installed${NC}"
fi

# 3. Установка Ollama (для Qwen)
echo ""
echo "3️⃣  Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    brew install ollama
else
    echo -e "${GREEN}✓ Ollama already installed${NC}"
fi

# Запуск Ollama сервиса
echo "Starting Ollama service..."
brew services start ollama
sleep 2

# 4. Python virtual environment
echo ""
echo "4️⃣  Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Активация venv
source venv/bin/activate

# Обновление pip
echo "Updating pip..."
pip install --upgrade pip

# Установка Python зависимостей
echo "Installing Python packages..."
pip install -r requirements.txt

echo -e "${GREEN}✓ Python packages installed${NC}"

# 5. Загрузка моделей
echo ""
echo "5️⃣  Downloading AI models..."

# Qwen модель через Ollama
echo "Downloading Qwen 2.5:3b..."
ollama pull qwen2.5:3b

echo -e "${GREEN}✓ Qwen model downloaded${NC}"

# Embedding модель
echo "Downloading Embedding model (nomic-embed-text)..."
ollama pull nomic-embed-text

echo -e "${GREEN}✓ Embedding model downloaded${NC}"

# Whisper модель
echo ""
echo "Downloading Whisper model (large-v3)..."
echo -e "${YELLOW}⚠️  This is a large download (~3GB), please wait...${NC}"

mkdir -p models/whisper
cd models/whisper

if [ ! -f "ggml-large-v3.bin" ]; then
    curl -L https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin -o ggml-large-v3.bin
    echo -e "${GREEN}✓ Whisper model downloaded${NC}"
else
    echo -e "${GREEN}✓ Whisper model already exists${NC}"
fi

cd ../..

# 6. Установка whisper.cpp
echo ""
echo "6️⃣  Building whisper.cpp..."

if [ ! -d "whisper.cpp" ]; then
    echo "Cloning whisper.cpp repository..."
    git clone https://github.com/ggml-org/whisper.cpp.git
    
    cd whisper.cpp
    
    echo "Building whisper.cpp with Core ML support (optimized for M1)..."
    make clean
    WHISPER_COREML=1 make -j
    
    echo -e "${GREEN}✓ whisper.cpp built successfully${NC}"
    cd ..
else
    echo -e "${GREEN}✓ whisper.cpp already exists${NC}"
fi

# 7. Создание .env файла
echo ""
echo "7️⃣  Setting up environment variables..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Created .env file from template${NC}"
    echo -e "${YELLOW}⚠️  Please edit .env and add your:${NC}"
    echo "    - TELEGRAM_BOT_TOKEN"
    echo "    - ALLOWED_USER_ID"
    echo ""
    echo "Get bot token from: @BotFather on Telegram"
    echo "Get your user ID from: @userinfobot on Telegram"
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# 8. Создание .gitkeep файлов
echo ""
echo "8️⃣  Creating directory structure..."

touch data/audio/.gitkeep
touch data/transcriptions/.gitkeep
touch data/logs/.gitkeep
mkdir -p data/qdrant_db

echo -e "${GREEN}✓ Directory structure ready${NC}"

# 9. Инициализация поиска (Reindex)
echo ""
echo "9️⃣  Initializing Semantic Search..."
if [ -d "notes" ]; then
    echo "Indexing existing notes..."
    python scripts/reindex.py
    echo -e "${GREEN}✓ Notes indexed${NC}"
else
    echo "No notes found, skipping indexing."
fi

# Финальное сообщение
echo ""
echo "================================"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Telegram credentials:"
echo "   nano .env"
echo ""
echo "2. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Run the bot:"
echo "   python main.py"
echo ""
echo "For more information, see README.md"
echo ""
