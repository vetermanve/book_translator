#!/bin/bash

# 📋 Загрузка переменных из .env файла

# Функция для безопасной загрузки .env
load_env() {
    if [ -f .env ]; then
        # Читаем .env построчно
        while IFS='=' read -r key value; do
            # Пропускаем комментарии и пустые строки
            if [[ ! "$key" =~ ^#.*$ ]] && [[ -n "$key" ]]; then
                # Убираем пробелы вокруг ключа
                key=$(echo "$key" | xargs)
                # Убираем кавычки из значения если есть
                value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
                # Экспортируем переменную
                export "$key=$value"
            fi
        done < .env
        
        # Проверяем, загружен ли API ключ
        if [ ! -z "$DEEPSEEK_API_KEY" ]; then
            # Показываем только первые и последние символы для безопасности
            masked_key="${DEEPSEEK_API_KEY:0:4}...${DEEPSEEK_API_KEY: -4}"
            echo "✅ Загружен API ключ из .env: $masked_key"
            return 0
        fi
    fi
    
    # Если .env не найден или ключ не загружен
    if [ -z "$DEEPSEEK_API_KEY" ]; then
        echo "⚠️ DEEPSEEK_API_KEY не найден в .env файле"
        
        # Проверяем, есть ли .env.example
        if [ -f .env.example ]; then
            echo "📝 Создайте .env файл на основе .env.example:"
            echo "   cp .env.example .env"
            echo "   Затем добавьте ваш API ключ в .env"
        fi
        
        return 1
    fi
    
    return 0
}

# Если скрипт запущен напрямую (не через source)
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    load_env
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "📋 Переменные окружения загружены:"
        echo "   • DEEPSEEK_API_KEY: установлен"
        
        # Показываем другие переменные если есть
        [ ! -z "$DEEPSEEK_API_ENDPOINT" ] && echo "   • DEEPSEEK_API_ENDPOINT: $DEEPSEEK_API_ENDPOINT"
        [ ! -z "$DEEPSEEK_MODEL" ] && echo "   • DEEPSEEK_MODEL: $DEEPSEEK_MODEL"
        [ ! -z "$MAX_WORKERS" ] && echo "   • MAX_WORKERS: $MAX_WORKERS"
        [ ! -z "$MAX_TOKENS" ] && echo "   • MAX_TOKENS: $MAX_TOKENS"
        [ ! -z "$TEMPERATURE" ] && echo "   • TEMPERATURE: $TEMPERATURE"
    else
        exit 1
    fi
fi