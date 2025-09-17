#!/bin/bash

# Скрипт для начала работы с новой книгой

echo "📚 Новый проект перевода"
echo "========================"
echo ""

# Проверяем, есть ли несохраненные изменения
if [ -f "book.pdf" ] || [ -d "extracted_fixed" ] || [ -d "translations" ]; then
    echo "⚠️  Обнаружен активный проект!"
    echo ""
    
    # Показываем статистику текущего проекта
    python3 -c "
from pathlib import Path

stats = []
if Path('book.pdf').exists():
    stats.append('📖 book.pdf')
    
if Path('extracted_fixed').exists():
    chapters = list(Path('extracted_fixed').glob('chapter_*.json'))
    if chapters:
        stats.append(f'📄 Извлечено глав: {len(chapters)}')
        
if Path('translations').exists():
    trans = list(Path('translations').glob('chapter_*_translated.json'))
    if trans:
        stats.append(f'🌐 Переведено глав: {len(trans)}')
        
if Path('output').exists():
    outputs = list(Path('output').glob('*.pdf'))
    if outputs:
        stats.append(f'📚 Выходных файлов: {len(outputs)}')

if stats:
    print('Текущее состояние:')
    for s in stats:
        print(f'  • {s}')
" 2>/dev/null
    
    echo ""
    echo -n "Сохранить текущий проект перед очисткой? (y/n): "
    read SAVE_CHOICE
    
    if [ "$SAVE_CHOICE" = "y" ] || [ "$SAVE_CHOICE" = "Y" ]; then
        ./save_project.sh
        if [ $? -ne 0 ]; then
            echo "❌ Ошибка при сохранении"
            exit 1
        fi
    fi
    
    echo ""
    echo "🧹 Очистка рабочего пространства..."
    python3 project_manager.py clean
    echo ""
fi

# Запрашиваем путь к новой книге
echo "Укажите путь к PDF книге для перевода:"
echo "(можно перетащить файл в терминал)"
echo ""
echo -n "Путь к PDF: "
read PDF_PATH

# Убираем кавычки если есть
PDF_PATH="${PDF_PATH%\'}"
PDF_PATH="${PDF_PATH#\'}"
PDF_PATH="${PDF_PATH%\"}"
PDF_PATH="${PDF_PATH#\"}"

# Проверяем существование файла
if [ ! -f "$PDF_PATH" ]; then
    echo ""
    echo "❌ Файл не найден: $PDF_PATH"
    exit 1
fi

# Проверяем что это PDF
if ! file "$PDF_PATH" | grep -q "PDF"; then
    echo ""
    echo "❌ Это не PDF файл!"
    exit 1
fi

# Копируем книгу в рабочую директорию
echo ""
echo "📋 Копирование книги..."
cp "$PDF_PATH" book.pdf

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при копировании"
    exit 1
fi

# Показываем информацию о книге
echo ""
echo "📖 Информация о книге:"
python3 -c "
import fitz
from pathlib import Path

doc = fitz.open('book.pdf')
pages = len(doc)
metadata = doc.metadata

print(f'  • Страниц: {pages}')

if metadata:
    if metadata.get('title'):
        print(f'  • Название: {metadata[\"title\"]}')
    if metadata.get('author'):
        print(f'  • Автор: {metadata[\"author\"]}')

size_mb = Path('book.pdf').stat().st_size / (1024 * 1024)
print(f'  • Размер: {size_mb:.1f} MB')

doc.close()
" 2>/dev/null

echo ""
echo "✅ Новый проект готов!"
echo ""
echo "Теперь вы можете:"
echo "  1. Запустить полный цикл:     ./run_all.sh"
echo "  2. Или выполнить по шагам:"
echo "     • Извлечь текст:           python3 01_extract_book.py"
echo "     • Извлечь диаграммы:       python3 02_extract_figures.py"  
echo "     • Перевести (25 потоков):  python3 03_translate_parallel.py --all"
echo "     • Скомпилировать книгу:    python3 04_compile_book.py"
echo ""
echo "💡 Совет: Не забудьте установить DEEPSEEK_API_KEY в окружении!"