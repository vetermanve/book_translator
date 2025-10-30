#!/bin/bash

# Скрипт для быстрого сохранения текущего проекта

echo "💾 Сохранение текущего проекта"
echo "=============================="
echo ""

# Проверяем наличие book.pdf
if [ ! -f "book.pdf" ]; then
    echo "❌ Файл book.pdf не найден!"
    echo "   Нет активного проекта для сохранения"
    exit 1
fi

# Получаем имя книги для предложения имени проекта
BOOK_NAME=$(python3 -c "
import fitz
try:
    doc = fitz.open('book.pdf')
    title = doc.metadata.get('title', '').strip()
    if title:
        # Очищаем от недопустимых символов
        title = ''.join(c for c in title if c.isalnum() or c in ' -_')[:30]
        print(title)
    else:
        print('book')
    doc.close()
except:
    print('book')
" 2>/dev/null || echo "book")

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEFAULT_NAME="${BOOK_NAME}_${TIMESTAMP}"

echo "📖 Обнаружена книга: $BOOK_NAME"
echo ""

# Запрашиваем имя проекта
echo -n "Имя проекта [$DEFAULT_NAME]: "
read PROJECT_NAME

if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="$DEFAULT_NAME"
fi

# Запрашиваем описание
echo -n "Описание (необязательно): "
read DESCRIPTION

echo ""
echo "🔄 Сохранение проекта '$PROJECT_NAME'..."
echo ""

# Сохраняем проект
python3 project_manager.py save "$PROJECT_NAME" "$DESCRIPTION"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Проект успешно сохранен!"
    echo ""
    echo "Сохранено:"
    echo "  • Извлеченные главы и диаграммы"
    echo "  • Переведенные тексты"
    echo "  • Аудио файлы (если есть)"
    echo "  • Адаптированные для аудио тексты (если есть)"
    echo "  • Фонетические замены (если есть)"
    echo ""
    echo "Для восстановления используйте:"
    echo "  ./load_project.sh $PROJECT_NAME"
    echo ""
    echo "Или посмотрите все проекты:"
    echo "  python3 project_manager.py list"
else
    echo ""
    echo "❌ Ошибка при сохранении проекта"
    exit 1
fi