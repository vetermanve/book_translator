#!/bin/bash

# Скрипт для быстрого применения фильтрации черного списка

echo "🔍 Применение фильтрации черного списка"
echo "========================================"
echo ""

# Проверяем наличие конфигурации
if [ ! -f "blacklist_config.json" ]; then
    echo "❌ Файл конфигурации blacklist_config.json не найден!"
    echo "   Создаем конфигурацию по умолчанию..."
    
    cat > blacklist_config.json << 'EOF'
{
  "blacklist": {
    "phrases": [
      "CMMI for Development, Version 1.3",
      "CMMI для разработки, версия 1.3",
      "CMMI for Development, версия 1.3"
    ],
    "symbols": ["®", "™", "©"],
    "patterns": []
  },
  "settings": {
    "remove_empty_paragraphs": true,
    "case_sensitive": false,
    "trim_whitespace": true,
    "min_paragraph_length": 10,
    "log_removals": true
  }
}
EOF
    echo "✅ Конфигурация создана"
fi

# Используем директорию translations
TRANS_DIR="translations"
echo "📚 Используем переводы из: $TRANS_DIR"

# Опции фильтрации
echo ""
echo "⚙️ Опции фильтрации:"
echo "   1) Создать отфильтрованную копию (translations_filtered)"
echo "   2) Заменить оригинальные файлы (с резервной копией)"
echo "   3) Заменить без резервной копии (осторожно!)"
read -p "Выберите опцию (1-3) [1]: " filter_option

case $filter_option in
    2)
        echo ""
        echo "💾 Создание резервной копии..."
        python3 06_postprocess_filter.py \
            --input-dir "$TRANS_DIR" \
            --output-dir translations_filtered \
            --replace
        ;;
    3)
        echo ""
        echo "⚠️ ВНИМАНИЕ: Оригинальные файлы будут перезаписаны!"
        read -p "   Продолжить? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 06_postprocess_filter.py \
                --input-dir "$TRANS_DIR" \
                --output-dir translations_filtered \
                --replace \
                --no-backup
        else
            echo "❌ Отменено"
            exit 1
        fi
        ;;
    *)
        echo ""
        python3 06_postprocess_filter.py \
            --input-dir "$TRANS_DIR" \
            --output-dir translations_filtered
        ;;
esac

# Проверяем результат
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Фильтрация завершена успешно!"
    
    # Предлагаем скомпилировать книгу
    echo ""
    read -p "📖 Скомпилировать книгу с отфильтрованным текстом? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 04_compile_book.py --use-filtered
        
        if [ $? -eq 0 ]; then
            echo "✅ Книга скомпилирована!"
            echo "📖 Файл: output/CMMI для разработки v1.3 (Полная версия).pdf"
        fi
    fi
    
    # Предлагаем создать аудиокнигу
    echo ""
    read -p "🎧 Создать аудиокнигу с отфильтрованным текстом? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./create_audiobook.sh
    fi
else
    echo "❌ Ошибка при фильтрации"
    exit 1
fi