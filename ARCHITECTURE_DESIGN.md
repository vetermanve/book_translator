# 🏗️ Архитектура портала BookTranslator Pro

## 📋 Анализ текущего решения

### ✅ Сильные стороны (сохраняем)
- **Параллельная обработка** - 25 потоков для перевода и генерации аудио
- **Контекстный перевод** - учет предыдущих глав и терминологии
- **Адаптивные аудиокниги** - преобразование в естественный пересказ
- **Фонетическая транскрипция** - правильное произношение терминов
- **Поддержка DeepSeek/Ollama** - гибкость в выборе модели

### ❌ Проблемы текущего решения
- Монолитные скрипты без разделения на сервисы
- Отсутствие БД - все в JSON файлах
- Нет веб-интерфейса для управления
- Нет очередей задач - только локальные потоки
- Отсутствие мониторинга и логирования

## 🎯 Целевая архитектура

### Микросервисы

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue.js)                         │
│  Dashboard │ Projects │ Editor │ Monitor │ Analytics │ Settings  │
└─────────────────┬───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                         │
│           Auth │ Rate Limiting │ Routing │ WebSockets           │
└─────────────────┬───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                         Service Mesh                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Book    │ │Translation│ │  Audio   │ │Analytics │          │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Storage  │ │  Prompt  │ │  Export  │ │Notification│         │
│  │ Service  │ │ Service  │ │ Service  │ │  Service  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────┬───────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────┐
│                    Infrastructure Layer                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │PostgreSQL│ │ RabbitMQ │ │  Redis   │ │   Minio  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

## 📦 Микросервисы - детальное описание

### 1. **Book Service** (Python/FastAPI)
Управление книгами и извлечение контента
```python
- POST /books/upload          # Загрузка PDF
- GET /books/{id}             # Информация о книге
- POST /books/{id}/extract    # Запуск извлечения
- GET /books/{id}/chapters    # Список глав
- GET /books/{id}/figures     # Список диаграмм
- DELETE /books/{id}          # Удаление книги
```

**Компоненты:**
- PDF Parser (PyMuPDF)
- Chapter Splitter
- Figure Extractor
- Metadata Analyzer

### 2. **Translation Service** (Python/FastAPI)
Управление переводами и промптами
```python
- POST /translations/create       # Создать перевод
- GET /translations/{id}         # Статус перевода
- POST /translations/{id}/start  # Запустить перевод
- PATCH /translations/{id}/pause # Пауза
- GET /translations/{id}/progress # Прогресс
- POST /translations/{id}/blocks # Перевести блок
```

**Компоненты:**
- Translation Worker Pool
- Context Manager
- DeepSeek/Ollama Client
- Progress Tracker
- Retry Manager

### 3. **Audio Service** (Python/FastAPI)
Генерация и адаптация аудиокниг
```python
- POST /audio/generate         # Создать аудиокнигу
- POST /audio/adapt           # Адаптировать текст
- GET /audio/{id}/status      # Статус генерации
- GET /audio/{id}/download    # Скачать MP3
- POST /audio/phonetics       # Генерация фонетики
```

**Компоненты:**
- Text Adapter
- Edge-TTS Client
- Audio Processor
- Phonetic Generator

### 4. **Prompt Service** (Python/FastAPI)
Управление промптами и шаблонами
```python
- GET /prompts                 # Список промптов
- POST /prompts                # Создать промпт
- PUT /prompts/{id}           # Обновить промпт
- GET /prompts/{id}/preview   # Предпросмотр
- POST /prompts/test          # Тестировать промпт
```

### 5. **Storage Service** (Python/FastAPI)
Работа с файлами через MinIO
```python
- POST /storage/upload         # Загрузить файл
- GET /storage/{id}/download   # Скачать файл
- DELETE /storage/{id}         # Удалить файл
- GET /storage/{id}/url        # Получить URL
```

### 6. **Analytics Service** (Python/FastAPI)
Статистика и метрики
```python
- GET /analytics/dashboard     # Дашборд
- GET /analytics/usage        # Использование API
- GET /analytics/costs        # Расходы на API
- GET /analytics/performance  # Производительность
```

### 7. **Notification Service** (Python/FastAPI)
Уведомления и WebSocket
```python
- WS /ws/{user_id}            # WebSocket подключение
- POST /notify/email          # Email уведомление
- POST /notify/webhook        # Webhook
```

## 💾 База данных PostgreSQL

### Основные таблицы

```sql
-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    api_keys JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Книги
CREATE TABLE books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(500),
    author VARCHAR(500),
    language VARCHAR(10),
    page_count INTEGER,
    file_path VARCHAR(500),
    metadata JSONB,
    status VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Главы
CREATE TABLE chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID REFERENCES books(id) ON DELETE CASCADE,
    number INTEGER,
    title VARCHAR(500),
    content TEXT,
    page_start INTEGER,
    page_end INTEGER,
    word_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Проекты перевода
CREATE TABLE translation_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID REFERENCES books(id),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255),
    source_lang VARCHAR(10),
    target_lang VARCHAR(10),
    settings JSONB,
    status VARCHAR(50) DEFAULT 'draft',
    progress FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Переводы
CREATE TABLE translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES translation_projects(id),
    chapter_id UUID REFERENCES chapters(id),
    original_text TEXT,
    translated_text TEXT,
    tokens_used INTEGER,
    cost DECIMAL(10, 4),
    duration_seconds INTEGER,
    status VARCHAR(50),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Блоки для параллельного перевода
CREATE TABLE translation_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    translation_id UUID REFERENCES translations(id),
    block_index INTEGER,
    original_text TEXT,
    translated_text TEXT,
    status VARCHAR(50),
    worker_id VARCHAR(50),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Промпты
CREATE TABLE prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255),
    type VARCHAR(50), -- translation, adaptation, phonetic
    template TEXT,
    variables JSONB,
    is_public BOOLEAN DEFAULT false,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Аудиокниги
CREATE TABLE audiobooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES translation_projects(id),
    voice_id VARCHAR(100),
    speed VARCHAR(10),
    adaptation_level VARCHAR(50),
    file_path VARCHAR(500),
    duration_seconds INTEGER,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Очередь задач
CREATE TABLE job_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50), -- extract, translate, audio
    payload JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    attempts INTEGER DEFAULT 0,
    worker_id VARCHAR(100),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Индексы для производительности
CREATE INDEX idx_books_user_id ON books(user_id);
CREATE INDEX idx_chapters_book_id ON chapters(book_id);
CREATE INDEX idx_translations_project_id ON translations(project_id);
CREATE INDEX idx_translations_status ON translations(status);
CREATE INDEX idx_job_queue_status ON job_queue(status, priority);
```

## 🐰 RabbitMQ - система очередей

### Очереди и обмены

```yaml
exchanges:
  - name: books
    type: topic
    durable: true
    
  - name: translations
    type: topic
    durable: true
    
  - name: audio
    type: topic
    durable: true

queues:
  # Извлечение книг
  - name: book.extract
    bindings:
      - exchange: books
        routing_key: book.extract.*
    
  # Перевод
  - name: translation.block
    bindings:
      - exchange: translations
        routing_key: translation.block.*
    arguments:
      x-max-priority: 10
      
  - name: translation.chapter
    bindings:
      - exchange: translations
        routing_key: translation.chapter.*
        
  # Аудио
  - name: audio.generate
    bindings:
      - exchange: audio
        routing_key: audio.generate.*
        
  - name: audio.adapt
    bindings:
      - exchange: audio
        routing_key: audio.adapt.*

# Dead Letter Queue для обработки ошибок
  - name: dlq.failed
    arguments:
      x-message-ttl: 86400000  # 24 часа
```

### Сообщения

```python
# Сообщение для перевода блока
{
    "job_id": "uuid",
    "project_id": "uuid",
    "chapter_id": "uuid",
    "block_index": 0,
    "text": "...",
    "context": {...},
    "settings": {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2000
    },
    "priority": 5,
    "retry_count": 0
}
```

## 🖥️ Frontend (Vue.js 3 + TypeScript)

### Страницы и компоненты

```
frontend/
├── pages/
│   ├── Dashboard.vue          # Главная панель
│   ├── Projects.vue           # Список проектов
│   ├── ProjectDetail.vue      # Детали проекта
│   ├── Editor.vue             # Редактор перевода
│   ├── PromptBuilder.vue      # Конструктор промптов
│   ├── AudioSettings.vue      # Настройки аудио
│   └── Analytics.vue          # Аналитика
│
├── components/
│   ├── BookUploader.vue       # Загрузка PDF
│   ├── ChapterList.vue        # Список глав
│   ├── TranslationEditor.vue  # Редактор с diff
│   ├── ProgressTracker.vue    # Прогресс перевода
│   ├── PromptEditor.vue       # Редактор промптов
│   ├── AudioPlayer.vue        # Плеер для превью
│   └── CostCalculator.vue     # Калькулятор стоимости
│
├── composables/
│   ├── useTranslation.ts      # Логика перевода
│   ├── useWebSocket.ts        # Real-time обновления
│   ├── useAudioGeneration.ts  # Генерация аудио
│   └── useProjectState.ts     # Состояние проекта
│
└── stores/
    ├── auth.ts                # Авторизация
    ├── projects.ts            # Проекты
    ├── translations.ts        # Переводы
    └── settings.ts            # Настройки
```

### Ключевые фичи UI

1. **Live Translation Editor**
   - Split view: оригинал / перевод
   - Inline редактирование
   - Diff highlighting
   - Контекстные подсказки
   - История изменений

2. **Prompt Builder**
   - Визуальный конструктор
   - Переменные и плейсхолдеры
   - Тестирование в реальном времени
   - Библиотека шаблонов
   - A/B тестирование промптов

3. **Progress Dashboard**
   - Реалтайм статус воркеров
   - График прогресса
   - Оценка времени завершения
   - Статистика токенов/стоимости
   - Heatmap активности

4. **Audio Studio**
   - Выбор голосов с превью
   - Настройка скорости/тона
   - Фонетический редактор
   - Уровни адаптации
   - Batch processing

## 🐳 Docker Compose конфигурация

```yaml
version: '3.9'

services:
  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://api-gateway:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    
  # API Gateway
  api-gateway:
    build: ./services/gateway
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
    
  # Микросервисы
  book-service:
    build: ./services/book
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MINIO_URL=http://minio:9000
    depends_on:
      - postgres
      - rabbitmq
      - minio
    volumes:
      - ./temp:/app/temp
    deploy:
      replicas: 2
    
  translation-service:
    build: ./services/translation
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - REDIS_URL=redis://redis:6379
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      - postgres
      - rabbitmq
      - redis
    deploy:
      replicas: 10  # Для параллельной обработки
    
  audio-service:
    build: ./services/audio
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MINIO_URL=http://minio:9000
    depends_on:
      - postgres
      - rabbitmq
      - minio
    deploy:
      replicas: 5
    
  # Workers для обработки очередей
  translation-worker:
    build: ./workers/translation
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      - postgres
      - rabbitmq
    deploy:
      replicas: 25  # Сохраняем 25 параллельных воркеров
    
  audio-worker:
    build: ./workers/audio
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/booktranslator
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MINIO_URL=http://minio:9000
    depends_on:
      - postgres
      - rabbitmq
      - minio
    deploy:
      replicas: 10
    
  # Инфраструктура
  postgres:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=booktranslator
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"  # Management UI
    environment:
      - RABBITMQ_DEFAULT_USER=admin
      - RABBITMQ_DEFAULT_PASS=admin
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"  # Console
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
    
  # Мониторинг
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/dashboards:/etc/grafana/provisioning/dashboards
    
volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
  minio_data:
  prometheus_data:
  grafana_data:
```

## 🚀 План миграции - поэтапная итерация

### Фаза 1: Базовая инфраструктура (1-2 недели)
1. **Настройка Docker Compose**
   - PostgreSQL + инициализация схемы
   - Redis для кеша
   - MinIO для файлов
   - RabbitMQ для очередей

2. **API Gateway**
   - FastAPI базовый сервер
   - Аутентификация JWT
   - CORS и rate limiting
   - Swagger документация

3. **Миграция данных**
   - Скрипт импорта JSON → PostgreSQL
   - Сохранение existing проектов
   - Backup стратегия

### Фаза 2: Core сервисы (2-3 недели)
1. **Book Service**
   - Портирование `01_extract_book.py`
   - Портирование `02_extract_figures.py`
   - REST API endpoints
   - Интеграция с MinIO

2. **Translation Service**
   - Портирование `03_translate_parallel.py`
   - Разделение на воркеры
   - RabbitMQ интеграция
   - Контекст менеджер

3. **Базовый Frontend**
   - Vue.js проект setup
   - Страница загрузки книг
   - Список проектов
   - Простой progress tracker

### Фаза 3: Advanced функционал (2-3 недели)
1. **Audio Service**
   - Портирование `05_create_audiobook.py`
   - Портирование `10_adapt_for_audio.py`
   - Фонетический процессор
   - Параллельная генерация

2. **Prompt Service**
   - CRUD для промптов
   - Версионирование
   - Тестирование промптов
   - Шаблоны и переменные

3. **Frontend Editor**
   - Split-view редактор
   - Inline editing
   - Diff visualization
   - Auto-save

### Фаза 4: Продвинутые фичи (2-3 недели)
1. **Analytics Service**
   - Метрики использования
   - Расчет стоимости
   - Performance tracking
   - Dashboards

2. **Notification Service**
   - WebSocket server
   - Email интеграция
   - Progress notifications
   - Completion alerts

3. **Advanced UI**
   - Prompt builder
   - Audio studio
   - Analytics dashboard
   - Settings management

### Фаза 5: Оптимизация и масштабирование (1-2 недели)
1. **Performance**
   - Кеширование Redis
   - Database оптимизация
   - CDN для статики
   - Lazy loading

2. **Monitoring**
   - Prometheus метрики
   - Grafana дашборды
   - Error tracking (Sentry)
   - Logs aggregation

3. **DevOps**
   - CI/CD pipeline
   - Kubernetes манифесты
   - Helm charts
   - Auto-scaling

## 🔑 Ключевые технологии

### Backend
- **FastAPI** - высокопроизводительный Python framework
- **SQLAlchemy** - ORM для PostgreSQL
- **Celery** - альтернатива для task queue
- **Pydantic** - валидация данных
- **aiohttp** - асинхронные HTTP запросы
- **PyMuPDF** - работа с PDF

### Frontend
- **Vue 3** - реактивный framework
- **TypeScript** - типизация
- **Pinia** - state management
- **TailwindCSS** - стилизация
- **Vite** - сборщик
- **Socket.io** - WebSocket client

### Infrastructure
- **PostgreSQL** - основная БД
- **Redis** - кеш и сессии
- **RabbitMQ** - очереди сообщений
- **MinIO** - S3-совместимое хранилище
- **Nginx** - reverse proxy
- **Docker** - контейнеризация

## 📊 Преимущества новой архитектуры

1. **Масштабируемость**
   - Горизонтальное масштабирование воркеров
   - Load balancing между сервисами
   - Автоскейлинг по нагрузке

2. **Надежность**
   - Retry механизмы
   - Dead letter queues
   - Circuit breakers
   - Health checks

3. **Производительность**
   - Параллельная обработка через RabbitMQ
   - Redis кеширование
   - Оптимизированные SQL запросы
   - CDN для статики

4. **User Experience**
   - Real-time обновления через WebSocket
   - Прогресс в реальном времени
   - Интерактивный редактор
   - Batch операции

5. **Maintainability**
   - Четкое разделение на сервисы
   - API-first подход
   - Автоматизированные тесты
   - Документация OpenAPI

## 🎯 MVP функционал (для первого релиза)

### Must Have
- ✅ Загрузка и парсинг PDF
- ✅ Создание проекта перевода
- ✅ Параллельный перевод (25 воркеров)
- ✅ Базовый веб-интерфейс
- ✅ Прогресс трекер
- ✅ Скачивание результата

### Should Have
- ⚡ Редактирование перевода
- ⚡ Управление промптами
- ⚡ Генерация аудиокниги
- ⚡ Базовая аналитика

### Nice to Have
- 🎨 Адаптивные аудиокниги
- 🎨 Фонетическая транскрипция
- 🎨 A/B тестирование промптов
- 🎨 Коллаборация

## 📈 Метрики успеха

- **Performance**: < 5 сек на страницу перевода
- **Reliability**: 99.9% uptime
- **Scalability**: 100+ одновременных переводов
- **UX**: < 3 клика до старта перевода
- **Cost**: < $0.01 за страницу перевода

## 🔧 Инструменты разработки

```bash
# Backend
poetry          # Dependency management
pytest          # Testing
black           # Code formatting
mypy            # Type checking
pre-commit      # Git hooks

# Frontend
pnpm            # Package manager
vitest          # Testing
eslint          # Linting
prettier        # Formatting
husky           # Git hooks

# DevOps
docker-compose  # Local development
kubectl         # Kubernetes
helm            # Package manager
terraform       # Infrastructure as code
```

---

Эта архитектура обеспечит:
- 📊 Полный контроль над процессом перевода
- 🚀 Масштабируемость до 100+ книг одновременно
- 💡 Интуитивный интерфейс управления
- 🔄 Реиспользование лучших наработок
- 📈 Аналитику и оптимизацию процессов