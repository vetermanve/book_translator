# 🚀 Настройка локальной модели через Ollama

## 📋 Быстрый старт

```bash
# 1. Установка и настройка Ollama с моделью
./setup_ollama.sh

# 2. Переключение на локальный режим в .env
echo "USE_LOCAL_MODEL=true" >> .env

# 3. Проверка работоспособности
python3 test_local_model.py

# 4. Запуск перевода
python3 03_translate_parallel.py --all
```

## 🔧 Детальная настройка

### Шаг 1: Установка Ollama

Запустите скрипт автоматической установки:

```bash
./setup_ollama.sh
```

Скрипт выполнит:
- ✅ Установку Ollama (если не установлен)
- ✅ Запуск сервера Ollama
- ✅ Загрузку выбранной модели
- ✅ Тестирование модели
- ✅ Обновление конфигурации .env

### Шаг 2: Выбор модели

При запуске `setup_ollama.sh` вам будет предложено выбрать модель:

1. **deepseek-coder:6.7b-instruct** (4GB) - Рекомендуется
   - Специализирована на коде и технической документации
   - Хорошо понимает контекст CMMI

2. **qwen2.5:7b** (4.4GB) - Хорошо для русского языка
   - Отличная поддержка русского языка
   - Универсальная модель

3. **mistral:7b** (4.1GB) - Универсальная
   - Баланс между качеством и скоростью
   - Хорошая общая производительность

4. **llama3.2:latest** (4.7GB) - Последняя версия
   - Самая современная архитектура
   - Лучшее качество, но требует больше ресурсов

### Шаг 3: Конфигурация .env

После установки в .env будут добавлены:

```bash
# Локальный режим Ollama
USE_LOCAL_MODEL=true
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=deepseek-coder:6.7b-instruct
```

### Шаг 4: Управление сервером

```bash
# Запуск сервера
./start_ollama.sh

# Остановка сервера
pkill ollama

# Проверка статуса
curl http://localhost:11434/api/tags
```

## 🧪 Тестирование

```bash
# Полный тест системы
python3 test_local_model.py

# Тест отдельного файла
python3 -c "
from deepseek_translator import DeepSeekTranslator
t = DeepSeekTranslator()
print(t.translate_text('Hello world'))
"
```

## ⚙️ Требования к системе

- **RAM**: Минимум 8GB (рекомендуется 16GB)
- **Диск**: 5-10GB свободного места для моделей
- **CPU**: Современный процессор (поддержка AVX2 желательна)
- **GPU**: Опционально (ускорит работу в 5-10 раз)

## 🎯 Производительность

Сравнение скорости перевода:

| Режим | Скорость | Стоимость | Качество |
|-------|----------|-----------|----------|
| Облачный API | ~2-3 сек/запрос | $0.14/1M токенов | Отличное |
| Локальный CPU | ~10-20 сек/запрос | Бесплатно | Хорошее |
| Локальный GPU | ~2-5 сек/запрос | Бесплатно | Хорошее |

## 📊 Использование GPU (опционально)

Если у вас есть NVIDIA GPU:

```bash
# Проверка поддержки GPU
nvidia-smi

# Запуск Ollama с GPU
OLLAMA_NUM_GPU=1 ollama serve

# Или установка по умолчанию
export OLLAMA_NUM_GPU=1
```

Для Mac с Apple Silicon GPU работает автоматически.

## 🔍 Решение проблем

### Сервер не запускается

```bash
# Проверить порт
lsof -i :11434

# Убить процесс если занят
kill -9 $(lsof -t -i:11434)

# Перезапустить
./start_ollama.sh
```

### Модель не загружается

```bash
# Загрузить вручную
ollama pull deepseek-coder:6.7b-instruct

# Проверить список моделей
ollama list
```

### Недостаточно памяти

```bash
# Использовать меньшую модель
ollama pull tinyllama:latest  # 637MB

# Или ограничить использование памяти
OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

## 📝 Переключение между режимами

```bash
# Переключиться на локальную модель
sed -i '' 's/USE_LOCAL_MODEL=false/USE_LOCAL_MODEL=true/' .env

# Вернуться к облачному API
sed -i '' 's/USE_LOCAL_MODEL=true/USE_LOCAL_MODEL=false/' .env
```

## 🎓 Дополнительные модели

Можно установить другие модели для экспериментов:

```bash
# Для перевода
ollama pull aya:8b  # Многоязычная модель

# Для кода
ollama pull codellama:7b
ollama pull starcoder2:7b

# Для русского языка
ollama pull saiga:7b  # Специализирована на русском
```

## 📚 Ресурсы

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Список моделей](https://ollama.ai/library)
- [DeepSeek Models](https://github.com/deepseek-ai)
- [Оптимизация производительности](https://github.com/ollama/ollama/blob/main/docs/faq.md)

---

💡 **Совет**: Для больших книг рекомендуется использовать GPU или запускать перевод ночью на CPU.