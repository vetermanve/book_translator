#!/bin/bash

# 🚀 Полный цикл перевода книги с оптимизациями v2.0

# Загружаем переменные из .env если есть
if [ -f .env ]; then
    set -a  # Автоматический экспорт переменных
    source .env
    set +a
fi

# Засекаем время начала
START_TIME=$(date +%s)

echo "📚 Запуск оптимизированного цикла перевода книги v2.0"
echo "====================================================="
echo "🚀 Последние улучшения:"
echo "  ✨ Сохранение переносов строк и форматирования"
echo "  🧠 Контекст 3+3 (3 абзаца до + 3 после для лучшего качества)"
echo "  ⚡ Оптимизированные промпты (10x меньше токенов)"
echo "  🔄 Параллельный перевод до 25 потоков"
echo "  🖼️ Правильная обработка изображений"
echo ""

# Активируем виртуальное окружение
if [ -d "venv" ]; then
    echo "🐍 Активация виртуального окружения..."
    source venv/bin/activate
fi

# Проверяем наличие book.pdf
if [ ! -f "book.pdf" ]; then
    echo "❌ Файл book.pdf не найден!"
    echo "   Поместите PDF книгу в текущую директорию"
    exit 1
fi

# 1. Извлечение текста с сохранением форматирования
echo "1️⃣ Извлечение текста с сохранением переносов строк..."
python3 01_extract_book.py  # Используем обновленный экстрактор
if [ $? -ne 0 ]; then
    echo "⚠️ Ошибка при извлечении, пробуем альтернативный экстрактор..."
    python3 01_reextract_book.py
    if [ $? -ne 0 ]; then
        echo "❌ Критическая ошибка при извлечении"
        exit 1
    fi
    EXTRACT_DIR="extracted_proper"
else
    EXTRACT_DIR="extracted_fixed"
fi
echo "✅ Текст извлечен (${EXTRACT_DIR})"
echo ""

# 2. Извлечение диаграмм
echo "2️⃣ Извлечение диаграмм..."
python3 02_extract_figures.py
if [ $? -ne 0 ]; then
    echo "❌ Ошибка при извлечении диаграмм"
    exit 1
fi
echo "✅ Диаграммы извлечены"
echo ""

# 3. Оптимизированный перевод с контекстом
echo "3️⃣ Запуск оптимизированного параллельного перевода..."
echo "   🧠 Контекст 3+3: каждая группа видит соседние абзацы"
echo "   ⚡ Оптимизированные промпты: 10x меньше токенов"
echo "   🔄 Параллельность: до 25 потоков одновременно"
echo "⚠️ Это может занять время в зависимости от размера книги"
echo ""

# Приоритет: параллельный перевод с новыми оптимизациями
python3 03_translate_parallel.py --all
translation_result=$?

if [ $translation_result -ne 0 ]; then
    echo "⚠️ Проблема с параллельным переводом, пробуем контекстный..."
    python3 03_translate_contextual.py
    if [ $? -ne 0 ]; then
        echo "⚠️ Проблема с контекстным переводом, пробуем базовый..."
        python3 archive/03_translate_simple.py
        if [ $? -ne 0 ]; then
            echo "❌ Все методы перевода не удались"
            exit 1
        fi
    fi
fi

echo "✅ Перевод завершен (translations)"
echo ""

# 4. Пост-процессинг - фильтрация черного списка (опционально)
echo ""
echo "4️⃣ Пост-процессинг переводов"

# Проверяем существование конфигурации черного списка
FILTERED_AVAILABLE=false
if [ -f "blacklist_config.json" ]; then
    echo "📋 Найдена конфигурация черного списка"
    read -p "   Применить фильтрацию? (y/n) [y]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo "🔍 Применение фильтров..."
        python3 06_postprocess_filter.py --input-dir translations --output-dir translations_filtered
        
        if [ $? -eq 0 ]; then
            echo "✅ Фильтрация завершена"
            # Используем отфильтрованные переводы для дальнейшей обработки
            FILTERED_AVAILABLE=true
        else
            echo "⚠️ Ошибка при фильтрации, используем оригинальные переводы"
        fi
    fi
else
    echo "📋 Конфигурация черного списка не найдена (blacklist_config.json)"
    echo "   Пропускаем этап фильтрации"
fi

# 5. Компиляция финальной книги
echo ""
echo "5️⃣ Компиляция финальной книги..."

# Используем отфильтрованные переводы если доступны
if [ "$FILTERED_AVAILABLE" = true ]; then
    python3 04_compile_book.py --use-filtered
    compile_result=$?
else
    python3 04_compile_book.py
    compile_result=$?
fi

if [ $compile_result -ne 0 ]; then
    echo "❌ Ошибка при компиляции"
    exit 1
fi
echo "✅ Книга скомпилирована"
echo ""

# 6. Проверка результата
echo "6️⃣ Проверка результата..."
if [ -f "output/CMMI для разработки v1.3 (Полная версия).pdf" ]; then
    file_size=$(ls -lh "output/CMMI для разработки v1.3 (Полная версия).pdf" | awk '{print $5}')
    echo "✅ PDF создан успешно (размер: ${file_size})"
else
    echo "⚠️ PDF не найден, но процесс завершился"
fi
echo ""

# 7. Генерация аудиокниги (опционально)
echo ""
read -p "🎧 Создать аудиокнигу? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🎙️ Генерация аудиокниги..."
    
    # Проверяем установлен ли edge-tts
    if ! python3 -c "import edge_tts" 2>/dev/null; then
        echo "⚠️ Устанавливаем edge-tts..."
        pip install edge-tts pydub
    fi
    
    # Проверяем установлен ли ffmpeg
    if ! command -v ffmpeg &> /dev/null; then
        echo "⚠️ ffmpeg не установлен!"
        echo "   macOS: brew install ffmpeg"
        echo "   Linux: apt install ffmpeg"
        echo "   Пропускаем генерацию аудиокниги"
    else
        # Запускаем генерацию с правильной директорией переводов
        # Фонетическая замена включена по умолчанию для правильного произношения
        if [ "$FILTERED_AVAILABLE" = true ]; then
            python3 05_create_audiobook.py --translations-dir translations_filtered --voice male --workers 25
        else
            python3 05_create_audiobook.py --voice male --workers 25
        fi
        
        if [ $? -eq 0 ]; then
            echo "✅ Аудиокнига создана: audiobook/audiobook_complete.mp3"
        else
            echo "⚠️ Проблема при создании аудиокниги"
        fi
    fi
fi

# Вычисляем время выполнения
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
DURATION_MIN=$((DURATION / 60))
DURATION_SEC=$((DURATION % 60))

echo ""
echo "🎉 Процесс завершен!"
echo "📖 Финальная книга: output/CMMI для разработки v1.3 (Полная версия).pdf"
if [ -f "audiobook/audiobook_complete.mp3" ]; then
    echo "🎧 Аудиокнига: audiobook/audiobook_complete.mp3"
fi
echo "⏱️ Время выполнения: ${DURATION_MIN} мин ${DURATION_SEC} сек"
echo ""
echo "📊 Примененные оптимизации v2.0:"
echo "  ✅ Сохранение переносов строк внутри абзацев"
echo "  ✅ Контекст 3+3 для лучшего качества перевода"
echo "  ✅ Оптимизированные промпты (10x экономия токенов)"
echo "  ✅ Параллельный перевод до 25 потоков"
echo "  ✅ Умная группировка абзацев с контекстом"
echo "  ✅ Фонетическая замена для правильного произношения в аудиокниге"
echo ""
echo "Структура проекта:"
echo "  📁 ${EXTRACT_DIR}/ - извлеченные главы"
echo "  📁 figures/ - извлеченные диаграммы"
echo "  📁 ${TRANSLATIONS_DIR}/ - переведенные главы"
echo "  📁 output/ - финальная книга"