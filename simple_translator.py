#!/usr/bin/env python3
"""
Простой последовательный переводчик для медленных моделей
"""

import json
import requests
from pathlib import Path
import time
from tqdm import tqdm

def translate_text(text, max_retries=3):
    """Переводит текст через Ollama API с меньшими чанками"""
    
    # Загружаем настройки
    env_settings = {}
    if Path('.env').exists():
        with open('.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    env_settings[key] = val.strip('"\'')
    
    model = env_settings.get('OLLAMA_MODEL', 'llama3.1:8b')
    
    # Простой промпт
    prompt = f"""Translate this text from English to Russian. Keep it natural and professional:

{text}

Russian translation:"""
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'temperature': 0.3,
                    'options': {
                        'num_predict': len(text) * 3,  # Русский текст обычно длиннее
                        'top_p': 0.9,
                        'top_k': 40
                    }
                },
                timeout=600  # 10 минут на блок
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"Ошибка API: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"Таймаут, попытка {attempt + 1}/{max_retries}")
        except Exception as e:
            print(f"Ошибка: {e}")
    
    return None

def main():
    print("=" * 60)
    print("ПРОСТОЙ ПЕРЕВОДЧИК ДЛЯ LLAMA")
    print("=" * 60)
    
    # Загружаем главу
    chapter_path = Path('extracted_fixed/chapter_000.json')
    if not chapter_path.exists():
        print("❌ Файл extracted_fixed/chapter_000.json не найден")
        return
    
    with open(chapter_path, 'r', encoding='utf-8') as f:
        chapter_data = json.load(f)
    
    paragraphs = chapter_data['paragraphs']
    print(f"📚 Загружено {len(paragraphs)} параграфов")
    
    # Группируем по 300 символов (меньшие блоки)
    groups = []
    current_group = []
    current_size = 0
    max_chars = 300  # Меньшие блоки для быстрого перевода
    
    for para in paragraphs:
        if current_size + len(para) > max_chars and current_group:
            groups.append('\n\n'.join(current_group))
            current_group = [para]
            current_size = len(para)
        else:
            current_group.append(para)
            current_size += len(para)
    
    if current_group:
        groups.append('\n\n'.join(current_group))
    
    print(f"📦 Создано {len(groups)} блоков для перевода")
    print(f"📏 Размер блока: ~{max_chars} символов")
    
    # Переводим
    translated_blocks = []
    start_time = time.time()
    
    print("\n🚀 Начинаем перевод...")
    for i, block in enumerate(tqdm(groups, desc="Перевод")):
        print(f"\n📝 Блок {i+1}/{len(groups)} ({len(block)} симв.)")
        
        translation = translate_text(block)
        if translation:
            translated_blocks.append(translation)
            print(f"✅ Переведено: {translation[:50]}...")
        else:
            print(f"❌ Не удалось перевести блок {i+1}")
            translated_blocks.append(block)  # Оставляем оригинал
        
        # Сохраняем прогресс каждые 10 блоков
        if (i + 1) % 10 == 0:
            save_progress(translated_blocks, i + 1, len(groups))
    
    # Сохраняем результат
    elapsed = time.time() - start_time
    output_dir = Path('translations')
    output_dir.mkdir(exist_ok=True)
    
    translation = {
        'chapter_num': 0,
        'title': chapter_data.get('title', 'Chapter 1'),
        'paragraphs': translated_blocks,
        'translation_time': elapsed,
        'blocks_count': len(groups)
    }
    
    output_file = output_dir / 'chapter_000_simple.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(translation, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Перевод завершен!")
    print(f"⏱️  Время: {elapsed/60:.1f} минут")
    print(f"📄 Файл: {output_file}")
    print(f"📊 Средняя скорость: {elapsed/len(groups):.1f} сек/блок")

def save_progress(blocks, current, total):
    """Сохраняет промежуточный прогресс"""
    progress_dir = Path('progress')
    progress_dir.mkdir(exist_ok=True)
    
    progress_file = progress_dir / 'translation_progress.json'
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump({
            'blocks': blocks,
            'current': current,
            'total': total,
            'timestamp': time.time()
        }, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Прогресс сохранен: {current}/{total}")

if __name__ == '__main__':
    main()