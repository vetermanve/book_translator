# 🚀 Оптимизация параллелизма в Python

## Проблема: Слабая загрузка CPU при параллельной обработке

### Причины:
1. **GIL (Global Interpreter Lock)** - только один поток может выполнять Python-код
2. **I/O-bound задачи** - большая часть времени уходит на ожидание сети
3. **ThreadPoolExecutor** - не дает настоящего параллелизма для CPU

## Текущая ситуация:

| Скрипт | Тип задачи | Используется | Загрузка CPU |
|--------|------------|--------------|--------------|
| 03_translate_parallel.py | I/O-bound (API) | ThreadPoolExecutor | ~5-15% |
| 05_create_audiobook.py | I/O-bound (TTS) | ThreadPoolExecutor | ~5-10% |

## Решения:

### 1. Для I/O-bound задач (текущие скрипты) - AsyncIO

```python
# Вместо ThreadPoolExecutor
import asyncio
import aiohttp

async def translate_async(session, text):
    async with session.post(url, json=data) as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [translate_async(session, text) for text in texts]
        results = await asyncio.gather(*tasks)
```

**Преимущества:**
- Один поток, но тысячи одновременных соединений
- Минимальный overhead
- Идеально для API-запросов

### 2. Для CPU-bound задач - ProcessPoolExecutor

```python
from concurrent.futures import ProcessPoolExecutor

# Для задач с тяжелыми вычислениями
with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
    results = executor.map(cpu_intensive_function, data)
```

**Преимущества:**
- Обходит GIL
- Использует все ядра CPU
- Настоящий параллелизм

### 3. Для смешанных задач - Гибридный подход

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def hybrid_processing():
    loop = asyncio.get_event_loop()
    
    # CPU-intensive в отдельном процессе
    with ProcessPoolExecutor() as executor:
        cpu_result = await loop.run_in_executor(
            executor, cpu_intensive_task, data
        )
    
    # I/O в async
    io_result = await fetch_from_api(cpu_result)
    
    return io_result
```

## Рекомендации для наших скриптов:

### Для перевода (03_translate_parallel.py):
```python
# Переписать на asyncio + aiohttp
# Можно обрабатывать 100+ запросов одновременно
```

### Для аудио (05_create_audiobook.py):
```python
# Уже использует asyncio для edge-tts
# Но можно улучшить батчинг
```

## Мониторинг загрузки:

### Linux/Mac:
```bash
# Общая загрузка
htop

# Загрузка Python процесса
top -p $(pgrep python3)

# Детальная статистика
iostat -x 1
```

### Профилирование Python:
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# ваш код
profiler.disable()
stats = pstats.Stats(profiler).sort_stats('cumulative')
stats.print_stats(10)
```

## Почему это нормально для наших задач:

✅ **Низкая загрузка CPU - это OK для I/O-bound задач!**

- API-запросы ограничены скоростью сети
- TTS генерация происходит на серверах Microsoft
- CPU простаивает, но это не bottleneck

❌ **Когда это проблема:**
- Обработка изображений
- Математические вычисления
- Парсинг больших объемов данных

## Итог:

Для наших задач (перевод и TTS) слабая загрузка CPU - это нормально, потому что:
1. Мы ждем ответов от внешних API
2. Вычислительная нагрузка минимальная
3. Bottleneck - это сеть, а не CPU

Если хотите видеть 100% загрузку CPU, нужны CPU-intensive задачи с ProcessPoolExecutor.