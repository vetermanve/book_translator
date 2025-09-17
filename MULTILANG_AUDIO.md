# 🌐 Мультиязычная поддержка в аудиокниге

## Описание

Генератор аудиокниги автоматически определяет английские термины в русском тексте и произносит их с правильным английским акцентом используя SSML разметку.

## Как это работает

1. **Автоматическое определение** английских терминов:
   - Аббревиатуры: CMMI, OPD, OPF, SEI, SCAMPI
   - Термины: Process Area, Maturity Level, Generic Goal
   - CamelCase: ProcessImprovement, ConfigurationManagement
   
2. **SSML разметка** для переключения языка:
   ```xml
   <speak xml:lang="ru-RU">
     Модель <lang xml:lang="en-US">CMMI</lang> включает...
   </speak>
   ```

3. **Результат**: 
   - Русский текст озвучивается русским голосом
   - Английские термины - с английским произношением

## Использование

### Включить (по умолчанию):
```bash
./create_audiobook.sh
# Выберите 'y' на вопрос о мультиязычной поддержке

# Или напрямую:
python3 05_create_audiobook.py --voice male
```

### Отключить при проблемах:
```bash
python3 05_create_audiobook.py --disable-multilang
```

## Примеры произношения

| Текст | Без SSML | С SSML |
|-------|----------|--------|
| CMMI | "цэ-эм-эм-и" | "си-эм-эм-ай" |
| Process Area | "процесс ареа" | "про́сес э́риа" |
| OPD | "о-пэ-дэ" | "оу-пи-ди" |

## Тестирование

```bash
# Быстрый тест
python3 test_quick_audio.py

# Полный тест
python3 test_multilang_audio.py
```

## Решение проблем

Если есть проблемы с SSML:
1. Используйте флаг `--disable-multilang`
2. Проверьте версию edge-tts: `pip install --upgrade edge-tts`
3. Убедитесь что нет конфликтов в тексте

## Поддерживаемые термины

Автоматически определяются:
- **Аббревиатуры модели**: CMMI, CMMI-DEV, CMMI-ACQ, CMMI-SVC
- **Процессные области**: CAR, CM, DAR, IPM, MA, OPD, OPF, OPM, OPP, OT, PI, PMC, PP, PPQA, QPM, RD, REQM, RSKM, SAM
- **Методы оценки**: SCAMPI A, SCAMPI B, SCAMPI C
- **Уровни**: Maturity Level 1-5, Capability Level 0-3
- **Элементы**: Generic Goal, Specific Goal, Generic Practice, Specific Practice
- **Организации**: SEI, Software Engineering Institute, Carnegie Mellon University
- **Методологии**: Agile, Scrum, Waterfall, DevOps

---

*Мультиязычная поддержка делает аудиокнигу профессиональной и приятной для прослушивания!*