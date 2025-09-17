#!/bin/bash

# 🔊 Генерация фонетических транскрипций для аудиокниги

# Загружаем переменные из .env если есть
if [ -f .env ]; then
    set -a  # Автоматический экспорт переменных
    source .env
    set +a
fi

echo "🔊 Генератор фонетических транскрипций v1.0"
echo "============================================"
echo ""
echo "Этот скрипт:"
echo "1. Извлечет английские термины из переводов"
echo "2. Сгенерирует фонетические транскрипции через DeepSeek"
echo "3. Создаст файл для использования в аудиокниге"
echo ""

# Проверка наличия переводов
if [ ! -d "translations" ]; then
    echo "❌ Директория translations не найдена!"
    echo "   Сначала выполните перевод книги"
    exit 1
fi

# Проверка API ключа
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️ Переменная DEEPSEEK_API_KEY не установлена"
    read -p "Введите API ключ DeepSeek: " api_key
    if [ -z "$api_key" ]; then
        echo "❌ API ключ необходим для работы"
        exit 1
    fi
    export DEEPSEEK_API_KEY="$api_key"
fi

# Шаг 1: Извлечение терминов
echo "1️⃣ Извлечение английских терминов из переводов..."
echo ""

python3 07_extract_terms.py --input-dir translations --output extracted_terms.json

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при извлечении терминов"
    exit 1
fi

# Показываем статистику
if [ -f "extracted_terms.json" ]; then
    total_terms=$(python3 -c "import json; data=json.load(open('extracted_terms.json')); print(data.get('total_unique_terms', 0))")
    echo ""
    echo "✅ Извлечено уникальных терминов: $total_terms"
fi

# Спрашиваем о продолжении
echo ""
read -p "Сгенерировать фонетические транскрипции? (y/n) [y]: " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "⏹️ Отменено пользователем"
    exit 0
fi

# Шаг 2: Генерация фонетики через DeepSeek
echo ""
echo "2️⃣ Генерация фонетических транскрипций через DeepSeek..."
echo "⚠️ Это может занять время и потребует API запросов"
echo ""

# Параметры генерации
BATCH_SIZE=20
WORKERS=5

read -p "Размер батча (по умолчанию $BATCH_SIZE): " user_batch
if [ ! -z "$user_batch" ]; then
    BATCH_SIZE=$user_batch
fi

read -p "Количество потоков (по умолчанию $WORKERS): " user_workers
if [ ! -z "$user_workers" ]; then
    WORKERS=$user_workers
fi

echo ""
echo "Параметры генерации:"
echo "  • Размер батча: $BATCH_SIZE терминов"
echo "  • Параллельных потоков: $WORKERS"
echo ""

# Запуск генерации
python3 08_generate_phonetics.py \
    --terms extracted_terms.json \
    --output phonetics.json \
    --batch-size $BATCH_SIZE \
    --workers $WORKERS

if [ $? -ne 0 ]; then
    echo "❌ Ошибка при генерации фонетики"
    exit 1
fi

# Проверка результата
if [ -f "phonetics.json" ]; then
    echo ""
    echo "✅ Фонетические транскрипции сохранены в phonetics.json"
    
    # Показываем примеры
    echo ""
    echo "📝 Примеры транскрипций:"
    python3 -c "
import json
data = json.load(open('phonetics.json'))
phonetics = data.get('phonetics', {})
examples = list(phonetics.items())[:5]
for term, trans in examples:
    print(f'  • {term} → {trans}')
"
fi

# Предложение использования
echo ""
echo "🎉 Готово!"
echo ""
echo "💡 Теперь можно использовать в аудиокниге:"
echo "   python3 05_create_audiobook.py --phonetics phonetics.json"
echo ""
echo "   или интерактивно:"
echo "   ./create_audiobook.sh"
echo ""
echo "📌 Файлы:"
echo "   • extracted_terms.json - извлеченные термины"
echo "   • phonetics.json - фонетические транскрипции"