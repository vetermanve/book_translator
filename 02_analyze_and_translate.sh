#!/bin/bash

# Умный переводчик с автоопределением контекста
echo "📚 ИНТЕЛЛЕКТУАЛЬНЫЙ ПЕРЕВОДЧИК С АВТОКОНТЕКСТОМ"
echo "==============================================="
echo ""

# Шаг 1: Экстракция книги
echo "📖 Шаг 1: Извлечение текста..."
if [ -f "extracted_content.json" ]; then
    echo "   ✓ Книга уже извлечена"
else
    python3 01_extract_book.py
fi

# Шаг 2: Анализ контекста
echo ""
echo "🔍 Шаг 2: Анализ контекста книги..."
python3 analyze_context.py

if [ $? -eq 0 ]; then
    echo "   ✅ Контекст определен и сохранен"
    
    # Показываем определенный контекст
    echo ""
    echo "📋 Определенный контекст:"
    python3 -c "
import yaml
with open('translation_context.yaml', 'r') as f:
    ctx = yaml.safe_load(f)
    print(f\"   Тип: {ctx.get('text_type', 'неопределен')}\")
    print(f\"   Область: {ctx.get('domain', 'общая')}\")
    print(f\"   Стиль: {ctx.get('style', {}).get('formality', 'нейтральный')}\")
    print(f\"   Аудитория: {ctx.get('style', {}).get('audience', 'общая')}\")
"
else
    echo "   ⚠️ Используется стандартный контекст"
fi

# Шаг 3: Перевод с учетом контекста
echo ""
echo "🌐 Шаг 3: Перевод с учетом контекста..."
python3 03_translate_parallel.py

echo ""
echo "✅ Перевод завершен с учетом автоматически определенного контекста!"