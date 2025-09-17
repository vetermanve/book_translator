#!/bin/bash

# Скрипт для проверки состояния текущего проекта

echo "📊 Состояние проекта"
echo "===================="
echo ""

# Проверяем наличие активного проекта
if [ ! -f "book.pdf" ]; then
    echo "❌ Нет активного проекта"
    echo ""
    echo "Используйте:"
    echo "  ./new_project.sh     - для начала нового проекта"
    echo "  ./load_project.sh    - для загрузки сохраненного проекта"
    exit 0
fi

# Показываем информацию о книге
echo "📖 Книга:"
python3 -c "
import fitz
from pathlib import Path

doc = fitz.open('book.pdf')
pages = len(doc)
metadata = doc.metadata

if metadata and metadata.get('title'):
    print(f'  {metadata[\"title\"]}')
else:
    print('  book.pdf')

print(f'  Страниц: {pages}')

size_mb = Path('book.pdf').stat().st_size / (1024 * 1024)
print(f'  Размер: {size_mb:.1f} MB')

doc.close()
" 2>/dev/null

echo ""

# Проверяем извлеченные главы
if [ -d "extracted_fixed" ]; then
    EXTRACTED_DIR="extracted_fixed"
elif [ -d "extracted" ]; then
    EXTRACTED_DIR="extracted"
else
    EXTRACTED_DIR=""
fi

if [ -n "$EXTRACTED_DIR" ]; then
    CHAPTER_COUNT=$(ls "$EXTRACTED_DIR"/chapter_*.json 2>/dev/null | wc -l)
    echo "📄 Извлечение:"
    echo "  Глав извлечено: $CHAPTER_COUNT"
    
    if [ -f "$EXTRACTED_DIR/metadata.json" ]; then
        PAGES=$(python3 -c "
import json
with open('$EXTRACTED_DIR/metadata.json', 'r') as f:
    data = json.load(f)
    print(data.get('total_pages', 0))
" 2>/dev/null)
        echo "  Страниц обработано: $PAGES"
    fi
else
    echo "📄 Извлечение: не выполнено"
    echo "  Запустите: python3 01_extract_book.py"
fi

echo ""

# Проверяем диаграммы
if [ -d "figures" ] && [ "$(ls -A figures/*.png 2>/dev/null)" ]; then
    FIGURE_COUNT=$(ls figures/*.png 2>/dev/null | wc -l)
    echo "🖼️  Диаграммы:"
    echo "  Извлечено: $FIGURE_COUNT"
else
    echo "🖼️  Диаграммы: не извлечены"
    echo "  Запустите: python3 02_extract_figures.py"
fi

echo ""

# Проверяем переводы
if [ -d "translations" ]; then
    TRANS_COUNT=$(ls translations/chapter_*_translated.json 2>/dev/null | wc -l)
    
    if [ "$TRANS_COUNT" -gt 0 ]; then
        echo "🌐 Перевод:"
        echo "  Глав переведено: $TRANS_COUNT из $CHAPTER_COUNT"
        
        # Подсчитываем процент
        if [ "$CHAPTER_COUNT" -gt 0 ]; then
            PERCENT=$((TRANS_COUNT * 100 / CHAPTER_COUNT))
            echo -n "  Прогресс: "
            
            # Рисуем прогресс-бар
            BAR_LENGTH=20
            FILLED=$((PERCENT * BAR_LENGTH / 100))
            
            echo -n "["
            for ((i=0; i<$FILLED; i++)); do echo -n "█"; done
            for ((i=$FILLED; i<$BAR_LENGTH; i++)); do echo -n "░"; done
            echo "] $PERCENT%"
        fi
    else
        echo "🌐 Перевод: не начат"
        echo "  Запустите: python3 03_translate_parallel.py --all"
    fi
else
    echo "🌐 Перевод: не начат"
    echo "  Запустите: python3 03_translate_parallel.py --all"
fi

echo ""

# Проверяем выходные файлы
if [ -d "output" ] && [ "$(ls -A output/*.pdf 2>/dev/null)" ]; then
    echo "📚 Выходные файлы:"
    for file in output/*.pdf; do
        SIZE_MB=$(du -m "$file" | cut -f1)
        echo "  • $(basename "$file") (${SIZE_MB} MB)"
    done
else
    echo "📚 Компиляция: не выполнена"
    echo "  Запустите: python3 04_compile_book.py"
fi

echo ""

# Проверяем текущий проект в менеджере
CURRENT_PROJECT=$(python3 -c "
from pathlib import Path
current_file = Path('projects_archive/.current')
if current_file.exists():
    with open(current_file, 'r') as f:
        print(f.read().strip())
" 2>/dev/null)

if [ -n "$CURRENT_PROJECT" ]; then
    echo "💾 Проект: $CURRENT_PROJECT"
else
    echo "💾 Проект: не сохранен"
    echo "  Для сохранения: ./save_project.sh"
fi

echo ""

# Предлагаем дальнейшие действия
echo "📋 Дальнейшие действия:"

if [ "$CHAPTER_COUNT" = "0" ]; then
    echo "  1. Извлечь текст: python3 01_extract_book.py"
elif [ "$TRANS_COUNT" = "0" ]; then
    echo "  1. Извлечь диаграммы: python3 02_extract_figures.py"
    echo "  2. Начать перевод: python3 03_translate_parallel.py --all"
elif [ "$TRANS_COUNT" -lt "$CHAPTER_COUNT" ]; then
    echo "  1. Продолжить перевод: python3 03_translate_parallel.py"
    echo "  2. Скомпилировать текущее: python3 04_compile_book.py"
else
    echo "  1. Скомпилировать книгу: python3 04_compile_book.py"
    echo "  2. Сохранить проект: ./save_project.sh"
fi