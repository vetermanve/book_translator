#!/bin/bash

# Скрипт для увеличения лимитов системы перед генерацией аудиокниги

echo "🔧 Настройка системных лимитов для генерации аудиокниги"
echo "========================================================="

# Текущие лимиты
echo ""
echo "📊 Текущие лимиты:"
echo "   Лимит открытых файлов: $(ulimit -n)"
echo "   Лимит процессов: $(ulimit -u)"

# Увеличиваем лимиты
echo ""
echo "⚙️ Увеличение лимитов..."

# macOS специфично
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Проверяем текущий лимит
    current_limit=$(ulimit -n)
    
    if [ "$current_limit" -lt 4096 ]; then
        # Пробуем увеличить
        ulimit -n 4096 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✅ Лимит файлов увеличен до: $(ulimit -n)"
        else
            echo "⚠️ Не удалось увеличить лимит файлов"
            echo "   Попробуйте выполнить:"
            echo "   sudo launchctl limit maxfiles 4096 4096"
            echo ""
            echo "   Или добавьте в /etc/sysctl.conf:"
            echo "   kern.maxfiles=65536"
            echo "   kern.maxfilesperproc=4096"
        fi
    else
        echo "✅ Лимит файлов уже достаточный: $current_limit"
    fi
else
    # Linux
    ulimit -n 4096 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✅ Лимит файлов увеличен до: $(ulimit -n)"
    else
        echo "⚠️ Не удалось увеличить лимит"
        echo "   Добавьте в /etc/security/limits.conf:"
        echo "   * soft nofile 4096"
        echo "   * hard nofile 8192"
    fi
fi

echo ""
echo "📊 Новые лимиты:"
echo "   Лимит открытых файлов: $(ulimit -n)"
echo "   Лимит процессов: $(ulimit -u)"

echo ""
echo "🎯 Рекомендации для генерации аудиокниги:"
echo "   • Используйте не более 10-15 потоков если лимит < 1024"
echo "   • Используйте 15-20 потоков если лимит 1024-2048"
echo "   • Используйте 20-25 потоков если лимит > 2048"
echo ""
echo "✅ Готово к генерации!"