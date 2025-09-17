#!/bin/bash

# Активация виртуального окружения
source venv/bin/activate

# Запуск параллельного переводчика
echo "🚀 Запуск параллельного переводчика с 10 потоками"
echo ""

# Проверка аргументов
if [ $# -eq 0 ]; then
    echo "📚 Будут переведены все непереведенные главы"
    python parallel_translator.py
elif [ "$1" == "--all" ] || [ "$1" == "-a" ]; then
    echo "📚 Будут переведены ВСЕ главы"
    python parallel_translator.py --all
else
    echo "📚 Будут переведены главы: $@"
    python parallel_translator.py $@
fi