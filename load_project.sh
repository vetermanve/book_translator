#!/bin/bash

# Скрипт для быстрой загрузки сохраненного проекта

echo "📂 Загрузка сохраненного проекта"
echo "================================"
echo ""

# Если указан аргумент, используем его как имя проекта
if [ -n "$1" ]; then
    PROJECT_NAME="$1"
    echo "🔄 Загрузка проекта '$PROJECT_NAME'..."
    python3 project_manager.py load "$PROJECT_NAME"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Проект загружен!"
        echo ""
        echo "Теперь можете:"
        echo "  • Продолжить перевод: python3 03_translate_parallel.py"
        echo "  • Скомпилировать книгу: python3 04_compile_book.py"
        echo "  • Запустить полный цикл: ./run_all.sh"
    else
        echo ""
        echo "❌ Ошибка при загрузке проекта"
        exit 1
    fi
else
    # Показываем список и даем выбрать
    echo "📚 Доступные проекты:"
    echo ""
    
    # Создаем временный файл для списка
    TEMP_FILE=$(mktemp)
    
    # Получаем список проектов
    python3 -c "
import json
from pathlib import Path
from datetime import datetime

projects_file = Path('projects_archive/projects.json')
if projects_file.exists():
    with open(projects_file, 'r') as f:
        projects = json.load(f)
    
    if projects:
        names = []
        for idx, (name, info) in enumerate(projects.items(), 1):
            created = datetime.fromisoformat(info['created']).strftime('%Y-%m-%d %H:%M')
            book = info['book']['title'] or 'Без названия'
            pages = info['book']['pages']
            translated = info['stats']['translated_chapters']
            total = info['stats']['total_chapters']
            
            print(f'{idx:2}. {name}')
            print(f'    📖 {book} ({pages} стр.)')
            print(f'    📅 {created} | 📊 Переведено: {translated}/{total}')
            
            if info.get('description'):
                print(f'    💬 {info[\"description\"]}')
            
            print()
            names.append(name)
        
        # Сохраняем имена в файл
        with open('$TEMP_FILE', 'w') as f:
            for name in names:
                f.write(name + '\\n')
    else:
        print('Нет сохраненных проектов')
        exit(1)
else:
    print('Нет сохраненных проектов')
    exit(1)
" 2>/dev/null
    
    # Проверяем, есть ли проекты
    if [ ! -s "$TEMP_FILE" ]; then
        echo "❌ Нет сохраненных проектов"
        rm -f "$TEMP_FILE"
        exit 1
    fi
    
    # Читаем список проектов
    readarray -t PROJECTS < "$TEMP_FILE"
    rm -f "$TEMP_FILE"
    
    # Запрашиваем выбор
    echo -n "Выберите номер проекта (1-${#PROJECTS[@]}): "
    read CHOICE
    
    # Проверяем корректность выбора
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt "${#PROJECTS[@]}" ]; then
        echo ""
        echo "❌ Неверный выбор"
        exit 1
    fi
    
    # Получаем имя проекта
    PROJECT_NAME="${PROJECTS[$((CHOICE-1))]}"
    
    echo ""
    echo "🔄 Загрузка проекта '$PROJECT_NAME'..."
    python3 project_manager.py load "$PROJECT_NAME"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Проект загружен!"
        echo ""
        echo "Теперь можете:"
        echo "  • Продолжить перевод: python3 03_translate_parallel.py"
        echo "  • Скомпилировать книгу: python3 04_compile_book.py"
        echo "  • Запустить полный цикл: ./run_all.sh"
    else
        echo ""
        echo "❌ Ошибка при загрузке проекта"
        exit 1
    fi
fi