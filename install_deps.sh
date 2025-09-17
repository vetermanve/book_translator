#!/bin/bash

# Установка зависимостей для генерации аудиокниги

echo "📦 Установка зависимостей для генерации аудиокниги"
echo "=================================================="
echo ""

# Проверяем наличие venv
if [ -d "venv" ]; then
    echo "✅ Найдено виртуальное окружение venv"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "✅ Найдено виртуальное окружение .venv"
    source .venv/bin/activate
else
    echo "⚠️ Виртуальное окружение не найдено"
    echo "   Создаем новое..."
    python3 -m venv venv
    source venv/bin/activate
fi

echo ""
echo "🔧 Установка Python пакетов..."

# Обновляем pip
pip install --upgrade pip

# Устанавливаем необходимые пакеты
pip install edge-tts
pip install pydub

echo ""
echo "✅ Python пакеты установлены"

# Проверяем ffmpeg
echo ""
echo "🔍 Проверка ffmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "✅ ffmpeg установлен"
else
    echo "❌ ffmpeg не найден!"
    echo ""
    echo "Установите ffmpeg:"
    echo "  macOS:  brew install ffmpeg"
    echo "  Linux:  apt install ffmpeg"
    echo "  Windows: скачайте с https://ffmpeg.org"
fi

echo ""
echo "🎉 Установка завершена!"
echo ""
echo "Теперь вы можете запустить:"
echo "  ./create_audiobook.sh"
echo ""
echo "Или напрямую:"
echo "  source venv/bin/activate"
echo "  python3 05_create_audiobook.py --help"