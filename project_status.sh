#!/bin/bash

# Скрипт для проверки текущего состояния проекта

echo "📊 Статус текущего проекта"
echo "=========================="
echo ""

# Проверяем наличие книги
if [ -f "book.pdf" ]; then
    echo "✅ Книга загружена: book.pdf"
    
    # Пытаемся получить информацию о книге
    python3 -c "
import fitz
try:
    doc = fitz.open('book.pdf')
    print(f'   Страниц: {len(doc)}')
    title = doc.metadata.get('title', '')
    if title:
        print(f'   Название: {title}')
    doc.close()
except:
    pass
" 2>/dev/null
else
    echo "❌ Книга не загружена"
fi

echo ""
echo "📂 Состояние директорий:"
echo ""

# Проверяем извлечение
if [ -d "extracted_fixed" ]; then
    COUNT=$(find extracted_fixed -name "chapter_*.json" 2>/dev/null | wc -l)
    echo "✅ Извлечено глав: $COUNT (extracted_fixed/)"
elif [ -d "extracted" ]; then
    COUNT=$(find extracted -name "chapter_*.json" 2>/dev/null | wc -l)
    echo "✅ Извлечено глав: $COUNT (extracted/)"
else
    echo "⏸️  Главы не извлечены"
fi

# Проверяем диаграммы
if [ -d "figures" ]; then
    COUNT=$(find figures -name "*.png" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "✅ Извлечено диаграмм: $COUNT"
    else
        echo "⏸️  Диаграммы не извлечены"
    fi
else
    echo "⏸️  Диаграммы не извлечены"
fi

# Проверяем переводы
if [ -d "translations" ]; then
    COUNT=$(find translations -name "chapter_*_translated.json" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "✅ Переведено глав: $COUNT"
    else
        echo "⏸️  Перевод не начат"
    fi
else
    echo "⏸️  Перевод не начат"
fi

# Проверяем аудио v1.0
if [ -d "audiobook" ]; then
    COUNT=$(find audiobook -name "*.mp3" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "✅ Создано аудио файлов v1.0: $COUNT"
    else
        echo "⏸️  Аудиокнига v1.0 не создана"
    fi
else
    echo "⏸️  Аудиокнига v1.0 не создана"
fi

# Проверяем адаптацию для аудио v2.0
if [ -d "audio_adapted" ]; then
    COUNT=$(find audio_adapted -name "chapter_*_translated_audio.json" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "✅ Адаптировано для аудио глав: $COUNT"
    else
        echo "⏸️  Адаптация для аудио не начата"
    fi
else
    echo "⏸️  Адаптация для аудио не начата"
fi

# Проверяем адаптированное аудио v2.0
if [ -d "audiobook_adapted" ]; then
    COUNT=$(find audiobook_adapted -name "*.mp3" 2>/dev/null | wc -l)
    if [ "$COUNT" -gt 0 ]; then
        echo "✅ Создано адаптированных аудио v2.0: $COUNT"
    else
        echo "⏸️  Адаптированная аудиокнига не создана"
    fi
else
    echo "⏸️  Адаптированная аудиокнига не создана"
fi

# Проверяем фонетику
if [ -f "phonetics.json" ]; then
    echo "✅ Фонетические замены настроены"
fi

# Проверяем выходные файлы
if [ -d "output" ]; then
    PDF_COUNT=$(find output -name "*.pdf" 2>/dev/null | wc -l)
    EPUB_COUNT=$(find output -name "*.epub" 2>/dev/null | wc -l)
    if [ "$PDF_COUNT" -gt 0 ] || [ "$EPUB_COUNT" -gt 0 ]; then
        echo "✅ Выходные файлы: PDF=$PDF_COUNT, EPUB=$EPUB_COUNT"
    else
        echo "⏸️  Финальная компиляция не выполнена"
    fi
else
    echo "⏸️  Финальная компиляция не выполнена"
fi

echo ""
echo "💡 Следующие шаги:"
echo ""

# Предлагаем следующие действия
if [ ! -f "book.pdf" ]; then
    echo "  1. Загрузите книгу: cp /path/to/your/book.pdf ./book.pdf"
elif [ ! -d "extracted_fixed" ] && [ ! -d "extracted" ]; then
    echo "  1. Извлеките текст: python3 01_extract_book.py"
elif [ ! -d "translations" ]; then
    echo "  1. Начните перевод: python3 03_translate_parallel.py --all"
else
    TRANS_COUNT=$(find translations -name "chapter_*_translated.json" 2>/dev/null | wc -l)
    TOTAL_COUNT=0
    
    if [ -d "extracted_fixed" ]; then
        TOTAL_COUNT=$(find extracted_fixed -name "chapter_*.json" 2>/dev/null | wc -l)
    elif [ -d "extracted" ]; then
        TOTAL_COUNT=$(find extracted -name "chapter_*.json" 2>/dev/null | wc -l)
    fi
    
    if [ "$TRANS_COUNT" -lt "$TOTAL_COUNT" ]; then
        echo "  1. Продолжите перевод: python3 03_translate_parallel.py"
    fi
    
    if [ ! -d "audiobook" ]; then
        echo "  2. Создайте аудиокнигу v1.0: python3 05_create_audiobook.py"
    fi
    
    if [ ! -d "audio_adapted" ]; then
        echo "  3. Адаптируйте для аудио v2.0: python3 10_adapt_for_audio.py"
    fi
    
    if [ ! -d "output" ]; then
        echo "  4. Скомпилируйте PDF: python3 04_compile_book.py"
    fi
fi

echo ""
echo "📦 Управление проектом:"
echo "  • Сохранить: ./save_project.sh"
echo "  • Загрузить: ./load_project.sh"
echo "  • Список: python3 project_manager.py list"
echo ""