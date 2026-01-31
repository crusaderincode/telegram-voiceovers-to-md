#!/bin/bash
# Скрипт для проверки статуса бота

# Определение корневой директории проекта
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_ROOT"

source venv/bin/activate 2>/dev/null || true

echo "🔍 AI Notes Bot - System Check"
echo "================================"
echo ""

# 1. Python environment
echo "1️⃣  Python Environment"
if [ -d "venv" ]; then
    echo "   ✓ Virtual environment exists"
    if [ -f "venv/bin/python" ]; then
        PYTHON_VERSION=$(venv/bin/python --version)
        echo "   ✓ Python: $PYTHON_VERSION"
    fi
else
    echo "   ❌ Virtual environment not found"
fi
echo ""

# 2. Dependencies
echo "2️⃣  System Dependencies"

# FFmpeg
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -n 1)
    echo "   ✓ FFmpeg installed"
else
    echo "   ❌ FFmpeg not found"
fi

# Ollama
if command -v ollama &> /dev/null; then
    echo "   ✓ Ollama installed"
    
    # Проверка сервиса
    if pgrep -x "ollama" > /dev/null; then
        echo "   ✓ Ollama service running"
    else
        echo "   ⚠️  Ollama service not running"
    fi
else
    echo "   ❌ Ollama not found"
fi

# whisper-cli
if command -v whisper-cli &> /dev/null; then
    echo "   ✓ whisper-cli installed"
else
    echo "   ❌ whisper-cli not found"
fi
echo ""

# 3. Models
echo "3️⃣  AI Models"

# Whisper
if [ -f "models/whisper/ggml-large-v3.bin" ]; then
    SIZE=$(du -h "models/whisper/ggml-large-v3.bin" | cut -f1)
    echo "   ✓ Whisper model: $SIZE"
else
    echo "   ❌ Whisper model not found"
fi

# Qwen
if ollama list 2>/dev/null | grep -q "qwen2.5:3b"; then
    echo "   ✓ Qwen model installed"
else
    echo "   ❌ Qwen model not found"
fi
echo ""

# 4. Configuration
echo "4️⃣  Configuration"

if [ -f ".env" ]; then
    echo "   ✓ .env file exists"
    
    # Проверка токена (не показываем сам токен)
    if grep -q "TELEGRAM_BOT_TOKEN=your_bot_token_here" .env; then
        echo "   ⚠️  Telegram token not configured"
    else
        echo "   ✓ Telegram token configured"
    fi
    
    # Проверка User ID
    if grep -q "ALLOWED_USER_ID=123456789" .env; then
        echo "   ⚠️  User ID not configured"
    else
        echo "   ✓ User ID configured"
    fi
else
    echo "   ❌ .env file not found"
fi
echo ""

# 5. Directories
echo "5️⃣  Directory Structure"

DIRS=("notes/идеи" "notes/жизнь" "notes/работа" "notes/инбокс" "data/audio" "data/transcriptions" "data/logs")

for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        COUNT=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "   ✓ $dir ($COUNT files)"
    else
        echo "   ❌ $dir not found"
    fi
done
echo ""

# 6. Disk space
echo "6️⃣  Resources"
DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}')
echo "   📊 Disk usage: $DISK_USAGE"

if command -v python &> /dev/null; then
    MEMORY=$(python -c "import psutil; print(f'{psutil.virtual_memory().percent:.1f}%')" 2>/dev/null || echo "N/A")
    echo "   🧠 Memory usage: $MEMORY"
fi
echo ""

echo "================================"
echo "✅ Check complete"
