# 📚 Инструкция по использованию системы перевода книг

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate

# Установка пакетов
pip install -r requirements.txt
```

### 2. Настройка API ключа (опционально)
Для качественного перевода через OpenAI API:

```bash
# Создайте файл .env
cp .env.example .env

# Откройте .env и добавьте ваш ключ:
OPENAI_API_KEY=sk-your-key-here
```

Получить ключ: https://platform.openai.com/api-keys

### 3. Запуск демо
```bash
python demo.py
```

## 📖 Основные команды

### Полный цикл перевода
```bash
# С API
python main.py full --pdf book.pdf --api-key YOUR_KEY --title "Название" --author "Автор"

# Без API (базовый перевод)
python main.py full --pdf book.pdf --no-api
```

### Пошаговое выполнение

#### 1. Извлечение содержимого
```bash
python main.py extract --pdf book.pdf
```
Результат:
- `extracted/` - JSON файлы с главами
- `images/` - извлеченные изображения
- `extracted/metadata.json` - метаданные книги

#### 2. Перевод
```bash
# Все главы с API
python main.py translate --api-key YOUR_KEY

# Без API (базовый словарный перевод)
python main.py translate --no-api

# Конкретные главы
python main.py translate --chapters 0 1 2 3 --api-key YOUR_KEY

# Продолжение прерванного перевода
python main.py translate  # автоматически продолжит с места остановки
```

#### 3. Компиляция
```bash
# Все форматы
python main.py compile

# Конкретный формат
python main.py compile --format fb2
python main.py compile --format pdf
python main.py compile --format epub

# С метаданными
python main.py compile --title "Моя книга" --author "Иван Иванов"
```

#### 4. Проверка статуса
```bash
python main.py status
```

## 🎯 Сценарии использования

### Сценарий 1: Быстрый перевод технической документации
```bash
# Извлечение и разбиение на главы по 30 страниц
python main.py extract --pdf manual.pdf

# Перевод с API
python main.py translate --api-key $OPENAI_API_KEY

# Компиляция в PDF для печати
python main.py compile --format pdf --title "Руководство"
```

### Сценарий 2: Перевод книги с сохранением прогресса
```bash
# Начало перевода
python main.py extract --pdf book.pdf
python main.py translate --chapters 0 1 2 3 4  # первые 5 глав

# На следующий день
python main.py translate --chapters 5 6 7 8 9  # следующие 5 глав

# Или автоматическое продолжение
python main.py translate  # продолжит с главы 5

# Проверка прогресса
python main.py status

# После завершения
python main.py compile --format fb2
```

### Сценарий 3: Тестовый перевод без API
```bash
# Для проверки работы системы без затрат на API
python main.py full --pdf book.pdf --no-api
```

## 📁 Структура файлов

После обработки создается следующая структура:

```
translater/
├── book.pdf                  # Исходный файл
├── extracted/                # Извлеченные данные
│   ├── chapter_000.json     # Главы в JSON
│   ├── chapter_001.json
│   └── metadata.json        # Метаданные книги
├── images/                   # Извлеченные изображения
│   ├── img_0000_00_xxx.png
│   └── img_0030_00_yyy.png
├── translations/             # Переведенные главы
│   ├── chapter_000_translated.json
│   └── chapter_001_translated.json
├── context/                  # Контекстные файлы
│   └── context_chapter_000.json
├── progress/                 # Прогресс перевода
│   └── translation_progress.json
└── output/                   # Готовые книги
    ├── book.fb2
    ├── book.pdf
    └── book.epub
```

## 🔧 Настройки

### Переменные окружения (.env)
```bash
# API ключи
OPENAI_API_KEY=sk-...        # OpenAI API
ANTHROPIC_API_KEY=sk-ant-...  # Claude API (альтернатива)

# Настройки перевода
TRANSLATION_MODEL=gpt-4       # Модель для перевода
MAX_TOKENS=2000               # Макс. токенов на запрос
TEMPERATURE=0.3               # Температура генерации (0-1)
```

### Параметры извлечения
При извлечении можно настроить размер глав:
```python
# В pdf_extractor_improved.py
extractor.extract_all(page_based_split=50)  # Главы по 50 страниц
```

## 🚨 Решение проблем

### Проблема: "No module named 'PIL'"
```bash
pip install Pillow
```

### Проблема: "PDF protected by password"
Используйте инструменты для снятия защиты PDF или попробуйте другой файл.

### Проблема: Не определяются главы
Система автоматически разобьет книгу по страницам, если не найдет оглавление.

### Проблема: Ошибка API при переводе
- Проверьте правильность API ключа
- Проверьте баланс в OpenAI
- Используйте `--no-api` для базового перевода

### Проблема: Изображения не сохраняются
Некоторые PDF могут иметь защищенные изображения. Система пропустит их.

## 💡 Советы

1. **Для больших книг**: Переводите по частям, используя `--chapters`
2. **Для экономии API**: Сначала протестируйте на 1-2 главах
3. **Для технических текстов**: Проверьте файлы контекста в `context/`
4. **Для продолжения работы**: Система автоматически сохраняет прогресс

## 📊 Мониторинг

Проверка прогресса:
```bash
# Общий статус
python main.py status

# Детальный прогресс
cat progress/translation_progress.json | python3 -m json.tool
```

## 🆘 Помощь

При возникновении проблем:
1. Проверьте логи в консоли
2. Убедитесь, что все зависимости установлены
3. Проверьте структуру PDF (некоторые форматы могут не поддерживаться)

## 🎉 Готово!

Теперь вы можете переводить любые PDF книги на русский язык с сохранением структуры и иллюстраций!