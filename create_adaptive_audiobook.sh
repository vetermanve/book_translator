#!/bin/bash

# 🎙️ Создание адаптивной аудиокниги с пересказом для слуха

# Загружаем переменные из .env если есть
if [ -f .env ]; then
    set -a  # Автоматический экспорт переменных
    source .env
    set +a
    
    # Проверяем что ключ загружен
    if [ ! -z "$DEEPSEEK_API_KEY" ]; then
        echo "✅ API ключ загружен из .env"
    fi
fi

echo "🎙️ Генератор адаптивной аудиокниги v2.0"
echo "========================================="
echo ""
echo "Этот режим создает аудиокнигу с адаптацией текста:"
echo "• Технический текст → живой профессиональный пересказ"
echo "• Объяснение терминов и аббревиатур"
echo "• Удаление ссылок и таблиц"
echo "• Разговорный стиль изложения"
echo ""

# Проверка зависимостей
if [ ! -d "translations" ]; then
    echo "❌ Директория translations не найдена!"
    echo "   Сначала выполните перевод книги"
    exit 1
fi

# Проверка API ключа (уже должен быть загружен из .env)
if [ -z "$DEEPSEEK_API_KEY" ]; then
    # Пробуем загрузить еще раз напрямую
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Если все еще нет ключа
    if [ -z "$DEEPSEEK_API_KEY" ]; then
        echo "⚠️ API ключ не найден"
        echo ""
        echo "Варианты решения:"
        echo "1. Создайте .env файл: cp .env.example .env"
        echo "2. Добавьте ключ в .env: DEEPSEEK_API_KEY=ваш_ключ"
        echo ""
        read -p "Или введите API ключ сейчас: " api_key
        if [ -z "$api_key" ]; then
            echo "❌ API ключ необходим для адаптации текста"
            exit 1
        fi
        export DEEPSEEK_API_KEY="$api_key"
    fi
fi

# Выбор режима
echo "📚 Выберите режим создания аудиокниги:"
echo ""
echo "1) 📖 Обычная аудиокнига (прямое озвучивание перевода)"
echo "2) 🎯 Адаптивная аудиокнига (пересказ для слуха)"
echo "3) 🚀 Полная адаптация (контекст + пересказ + фонетика)"
echo ""
read -p "Выбор (1-3) [2]: " mode_choice

case $mode_choice in
    1)
        MODE="standard"
        echo "   Выбран режим: Обычная аудиокнига"
        ;;
    3)
        MODE="full"
        echo "   Выбран режим: Полная адаптация"
        ;;
    *)
        MODE="adaptive"
        echo "   Выбран режим: Адаптивная аудиокнига"
        ;;
esac

# Стандартный режим - просто запускаем обычную генерацию
if [ "$MODE" == "standard" ]; then
    echo ""
    echo "🎧 Запуск стандартной генерации аудиокниги..."
    ./create_audiobook.sh
    exit $?
fi

# ШАГ 1: Извлечение контекста книги (для полного режима)
if [ "$MODE" == "full" ]; then
    echo ""
    echo "1️⃣ Анализ контекста книги..."
    echo "   Извлекаем информацию о теме, аудитории и структуре"
    
    python3 09_extract_book_context.py \
        --input-dir extracted_fixed \
        --output book_context.json
    
    if [ $? -ne 0 ]; then
        echo "⚠️ Не удалось извлечь контекст, продолжаем без него"
        CONTEXT_FLAG=""
    else
        CONTEXT_FLAG="--context book_context.json"
        
        # Показываем извлеченный контекст
        if [ -f "book_context.json" ]; then
            echo ""
            echo "📖 Контекст книги:"
            python3 -c "
import json
data = json.load(open('book_context.json'))
print(f\"  • Технический уровень: {data.get('technical_level', 'неизвестно')}\")
print(f\"  • Целевая аудитория: {data.get('target_audience', 'неизвестно')}\")
if data.get('structure'):
    print(f\"  • Глав: {data['structure'].get('total_chapters', 0)}\")
"
        fi
    fi
else
    CONTEXT_FLAG=""
fi

# ШАГ 2: Адаптация текста для аудио
echo ""
echo "2️⃣ Адаптация текста для восприятия на слух..."
echo ""

# Параметры адаптации
echo "⚙️ Настройки адаптации:"
echo ""
echo "Размер группы параграфов для обработки:"
echo "  3 - Детальная адаптация (медленнее, точнее)"
echo "  5 - Сбалансированная (рекомендуется)"
echo "  7 - Быстрая адаптация (быстрее, менее детально)"
echo ""
read -p "Выбор (3-7) [5]: " group_size
if [ -z "$group_size" ]; then
    GROUP_SIZE=5
else
    GROUP_SIZE=$group_size
fi

read -p "Количество параллельных потоков (1-10) [5]: " workers
if [ -z "$workers" ]; then
    WORKERS=5
else
    WORKERS=$workers
fi

# Выбор источника для адаптации
ADAPT_SOURCE="translations"
if [ -d "translations_filtered" ] && [ "$(ls -A translations_filtered)" ]; then
    echo ""
    echo "📋 Найдены отфильтрованные переводы"
    read -p "   Использовать их для адаптации? (y/n) [y]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        ADAPT_SOURCE="translations_filtered"
    fi
fi

echo ""
echo "📝 Параметры адаптации:"
echo "   • Источник: $ADAPT_SOURCE"
echo "   • Группа параграфов: $GROUP_SIZE"
echo "   • Параллельных потоков: $WORKERS"
echo ""

# Тестовый режим
read -p "Сначала протестировать на одной главе? (y/n) [n]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🧪 Тестовая адаптация первой главы..."
    python3 10_adapt_for_audio.py \
        --input-dir "$ADAPT_SOURCE" \
        --output-dir audio_adapted \
        --group-size "$GROUP_SIZE" \
        $CONTEXT_FLAG \
        --test
    
    echo ""
    read -p "Продолжить с полной адаптацией? (y/n): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "⏹️ Отменено пользователем"
        exit 0
    fi
fi

# Полная адаптация
echo ""
echo "🔄 Запуск полной адаптации текста..."
echo "⚠️ Это может занять значительное время"
echo ""

START_TIME=$(date +%s)

python3 10_adapt_for_audio.py \
    --input-dir "$ADAPT_SOURCE" \
    --output-dir audio_adapted \
    --group-size "$GROUP_SIZE" \
    --workers "$WORKERS" \
    $CONTEXT_FLAG

ADAPT_RESULT=$?

END_TIME=$(date +%s)
ADAPT_DURATION=$((END_TIME - START_TIME))
ADAPT_MIN=$((ADAPT_DURATION / 60))
ADAPT_SEC=$((ADAPT_DURATION % 60))

if [ $ADAPT_RESULT -ne 0 ]; then
    echo "❌ Ошибка при адаптации текста"
    exit 1
fi

echo ""
echo "✅ Адаптация завершена за ${ADAPT_MIN} мин ${ADAPT_SEC} сек"
echo ""

# ШАГ 3: Генерация фонетических транскрипций (опционально)
echo "3️⃣ Фонетические транскрипции"
echo ""
read -p "Сгенерировать фонетические транскрипции для терминов? (y/n) [y]: " -n 1 -r
echo ""

PHONETICS_FLAG=""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    # Извлекаем термины из адаптированного текста
    echo "   Извлечение английских терминов..."
    python3 07_extract_terms.py \
        --input-dir audio_adapted \
        --output extracted_terms_audio.json
    
    if [ $? -eq 0 ] && [ -f "extracted_terms_audio.json" ]; then
        # Генерируем фонетику
        echo "   Генерация фонетических транскрипций..."
        python3 08_generate_phonetics.py \
            --terms extracted_terms_audio.json \
            --output phonetics_audio.json \
            --batch-size 20 \
            --workers 3
        
        if [ -f "phonetics_audio.json" ]; then
            PHONETICS_FLAG="--phonetics phonetics_audio.json"
            echo "   ✅ Фонетические транскрипции готовы"
        fi
    fi
fi

# ШАГ 4: Генерация аудиокниги
echo ""
echo "4️⃣ Генерация аудиокниги из адаптированного текста..."
echo ""

# Выбор голоса
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

# Скорость речи для адаптированного текста
echo ""
echo "⚡ Скорость речи (для пересказа рекомендуется нормальная):"
echo "   1) Медленная (-10%)"
echo "   2) Нормальная (0%)"
echo "   3) Чуть быстрее (+10%)"
read -p "Выбор (1-3) [2]: " speed_choice

case $speed_choice in
    1)
        RATE="-10%"
        ;;
    3)
        RATE="+10%"
        ;;
    *)
        RATE="+0%"
        ;;
esac

# Количество потоков для аудио
echo ""
read -p "🔄 Количество параллельных потоков для аудио (1-50) [25]: " audio_workers
if [ -z "$audio_workers" ]; then
    AUDIO_WORKERS=25
else
    AUDIO_WORKERS=$audio_workers
fi

echo ""
echo "🚀 Запуск генерации аудиокниги..."
echo "================================"

START_TIME=$(date +%s)

# Запуск с адаптированными текстами
python3 05_create_audiobook.py \
    --translations-dir audio_adapted \
    --voice "$VOICE" \
    --rate "$RATE" \
    --workers "$AUDIO_WORKERS" \
    --paragraphs-per-group 3 \
    $PHONETICS_FLAG

AUDIO_RESULT=$?

END_TIME=$(date +%s)
AUDIO_DURATION=$((END_TIME - START_TIME))
AUDIO_MIN=$((AUDIO_DURATION / 60))
AUDIO_SEC=$((AUDIO_DURATION % 60))

echo ""
echo "⏱️ Время генерации аудио: ${AUDIO_MIN} мин ${AUDIO_SEC} сек"

if [ $AUDIO_RESULT -eq 0 ]; then
    echo ""
    echo "🎉 Адаптивная аудиокнига успешно создана!"
    echo ""
    echo "📊 Статистика:"
    echo "   • Режим: $MODE"
    echo "   • Адаптация текста: ${ADAPT_MIN} мин"
    echo "   • Генерация аудио: ${AUDIO_MIN} мин"
    
    TOTAL_MIN=$((ADAPT_MIN + AUDIO_MIN))
    echo "   • Общее время: ${TOTAL_MIN} минут"
    echo ""
    echo "📁 Результаты:"
    echo "   • audio_adapted/ - адаптированный текст"
    echo "   • audiobook/audiobook_complete.mp3 - финальная аудиокнига"
    
    if [ -f "book_context.json" ]; then
        echo "   • book_context.json - контекст книги"
    fi
    
    if [ -f "phonetics_audio.json" ]; then
        echo "   • phonetics_audio.json - фонетические транскрипции"
    fi
    
    # Размер файла
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
            ffplay -autoexit -t 30 "audiobook/audiobook_complete.mp3" 2>/dev/null || \
            afplay -t 30 "audiobook/audiobook_complete.mp3" 2>/dev/null || \
            echo "   Не удалось воспроизвести"
        fi
    fi
    
    echo ""
    echo "💡 Особенности адаптивной версии:"
    echo "   • Технические термины объяснены простым языком"
    echo "   • Удалены ссылки на разделы и рисунки"
    echo "   • Списки преобразованы в связный текст"
    echo "   • Добавлены связующие фразы между идеями"
    echo "   • Стиль: эксперт объясняет коллеге"
    
else
    echo "❌ Ошибка при создании аудиокниги"
    exit 1
fi