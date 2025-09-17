#!/bin/bash

# 🎧 Быстрый запуск генерации аудиокниги

echo "🎧 Генератор аудиокниги v1.0"
echo "============================"

# Проверяем наличие переводов
if [ ! -d "translations" ]; then
    echo "❌ Не найдена директория с переводами!"
    echo "   Сначала выполните перевод книги"
    exit 1
fi

# Проверяем, есть ли отфильтрованные переводы
if [ -d "translations_filtered" ] && [ "$(ls -A translations_filtered)" ]; then
    echo "📋 Найдены отфильтрованные переводы"
    read -p "   Использовать их? (y/n) [y]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        TRANSLATIONS_DIR="translations_filtered"
    else
        TRANSLATIONS_DIR="translations"
    fi
else
    TRANSLATIONS_DIR="translations"
fi

echo "📁 Используем переводы из: ${TRANSLATIONS_DIR}"

# Проверяем зависимости
echo ""
echo "🔍 Проверка зависимостей..."

# Проверяем Python модули
if ! python3 -c "import edge_tts" 2>/dev/null; then
    echo "⚠️ edge-tts не установлен"
    read -p "   Установить? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install edge-tts pydub
    else
        echo "❌ Отмена. Установите: pip install edge-tts pydub"
        exit 1
    fi
else
    echo "✅ edge-tts установлен"
fi

# Проверяем ffmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️ ffmpeg не установлен!"
    echo "   Установка:"
    echo "   • macOS: brew install ffmpeg"
    echo "   • Ubuntu/Debian: apt install ffmpeg"
    echo "   • CentOS/RHEL: yum install ffmpeg"
    read -p "   Продолжить без ffmpeg? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ ffmpeg установлен"
fi

# Выбор голоса
echo ""
echo "🎤 Выберите голос для озвучки:"
echo "   1) Дмитрий (мужской)"
echo "   2) Светлана (женский)"
read -p "Выбор (1-2) [1]: " voice_choice

case $voice_choice in
    2)
        VOICE="female"
        echo "   Выбрана Светлана"
        ;;
    *)
        VOICE="male"
        echo "   Выбран Дмитрий"
        ;;
esac

# Настройка скорости
echo ""
echo "⚡ Скорость речи:"
echo "   1) Медленная (-25%)"
echo "   2) Нормальная (0%)"
echo "   3) Быстрая (+25%)"
read -p "Выбор (1-3) [2]: " speed_choice

case $speed_choice in
    1)
        RATE="-25%"
        echo "   Выбрана медленная скорость"
        ;;
    3)
        RATE="+25%"
        echo "   Выбрана быстрая скорость"
        ;;
    *)
        RATE="+0%"
        echo "   Выбрана нормальная скорость"
        ;;
esac

# Проверяем системные лимиты
echo ""
current_limit=$(ulimit -n)
echo "📊 Текущий лимит открытых файлов: $current_limit"

if [ "$current_limit" -lt 1024 ]; then
    echo "⚠️ Низкий лимит файлов! Рекомендуется не более 10 потоков"
    DEFAULT_WORKERS=10
elif [ "$current_limit" -lt 2048 ]; then
    echo "⚠️ Средний лимит файлов. Рекомендуется не более 15 потоков"
    DEFAULT_WORKERS=15
else
    echo "✅ Лимит файлов достаточный для 25 потоков"
    DEFAULT_WORKERS=25
fi

# Количество потоков
echo ""
read -p "🔄 Количество параллельных потоков (1-50) [$DEFAULT_WORKERS]: " workers
if [ -z "$workers" ]; then
    WORKERS=$DEFAULT_WORKERS
else
    WORKERS=$workers
fi
echo "   Используется $WORKERS потоков"

# Предупреждение если слишком много потоков
if [ "$WORKERS" -gt 15 ] && [ "$current_limit" -lt 2048 ]; then
    echo ""
    echo "⚠️ ВНИМАНИЕ: Много потоков при низком лимите файлов!"
    echo "   Возможна ошибка 'Too many open files'"
    echo "   Рекомендуется запустить ./fix_limits.sh"
    read -p "   Продолжить? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Фонетическая замена
echo ""
echo "🔤 Фонетическая замена терминов:"
echo "   Английские термины (CMMI, Process Area и т.д.)"
echo "   будут заменены на русскую транскрипцию"
echo "   для правильного произношения"
read -p "   Включить? (y/n) [y]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    PHONETIC_FLAG="--disable-phonetic"
    echo "   Фонетическая замена отключена"
else
    PHONETIC_FLAG=""
    echo "   Фонетическая замена включена"
fi

# Запуск генерации
echo ""
echo "🚀 Запуск генерации аудиокниги..."
echo "================================"

START_TIME=$(date +%s)

python3 05_create_audiobook.py \
    --translations-dir "${TRANSLATIONS_DIR}" \
    --voice "${VOICE}" \
    --rate "${RATE}" \
    --workers "${WORKERS}" \
    ${PHONETIC_FLAG}

RESULT=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

echo ""
echo "⏱️ Время генерации: ${DURATION_MIN} мин ${DURATION_SEC} сек"

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "🎉 Аудиокнига успешно создана!"
    echo "📁 Расположение файлов:"
    echo "   • audiobook/audiobook_complete.mp3 - полная аудиокнига"
    echo "   • audiobook/temp_audio/ - отдельные главы"
    echo "   • audiobook/audiobook_metadata.json - метаданные"
    
    # Показываем размер файла
    if [ -f "audiobook/audiobook_complete.mp3" ]; then
        FILE_SIZE=$(ls -lh "audiobook/audiobook_complete.mp3" | awk '{print $5}')
        echo ""
        echo "📊 Размер аудиокниги: ${FILE_SIZE}"
    fi
    
    # Предлагаем воспроизвести
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo ""
        read -p "🔊 Воспроизвести начало? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Воспроизводим первые 30 секунд
            ffplay -autoexit -t 30 "audiobook/audiobook_complete.mp3" 2>/dev/null || \
            afplay -t 30 "audiobook/audiobook_complete.mp3" 2>/dev/null || \
            echo "   Не удалось воспроизвести"
        fi
    fi
else
    echo "❌ Ошибка при создании аудиокниги"
    exit 1
fi