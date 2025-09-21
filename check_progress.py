#!/usr/bin/env python3
"""Проверка прогресса перевода"""

import json
from pathlib import Path
import time

# Ищем сохраненные переводы
translations_dir = Path('translations')
if translations_dir.exists():
    translations = list(translations_dir.glob('chapter_*.json'))
    if translations:
        print(f"✅ Найдено {len(translations)} переведенных глав:")
        for t in sorted(translations)[:5]:
            with open(t, 'r', encoding='utf-8') as f:
                data = json.load(f)
                paragraphs = data.get('paragraphs', [])
                if paragraphs:
                    print(f"\n📄 {t.name}:")
                    print(f"   Параграфов: {len(paragraphs)}")
                    # Показываем первый переведенный параграф
                    first_para = paragraphs[0] if isinstance(paragraphs[0], str) else str(paragraphs[0])
                    print(f"   Начало: {first_para[:100]}...")
    else:
        print("❌ Переведенных глав пока нет в папке translations/")
else:
    print("❌ Папка translations не найдена")

# Проверяем временные файлы
temp_files = list(Path('.').glob('**/temp_translation_*.json'))
if temp_files:
    print(f"\n🔄 Найдено {len(temp_files)} временных файлов")

# Проверяем progress
progress_dir = Path('progress')  
if progress_dir.exists():
    progress_files = list(progress_dir.glob('*.json'))
    if progress_files:
        print(f"\n📊 Найдено {len(progress_files)} файлов прогресса")
        for p in progress_files[:3]:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"   {p.name}: {data.get('current', 0)}/{data.get('total', 0)} блоков")
            except:
                pass