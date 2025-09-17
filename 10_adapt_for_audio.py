#!/usr/bin/env python3
"""
Адаптация технического текста для восприятия на слух
Преобразует формальный технический текст в разговорный стиль пересказа
"""

import json
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Загружаем переменные из .env если есть
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                # Убираем кавычки если есть
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value

# Добавляем путь к deepseek_translator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from deepseek_translator import DeepSeekTranslator


class AudioTextAdapter:
    def __init__(self, api_key: str = None, context_file: str = None):
        """Инициализация адаптера текста для аудио"""
        self.translator = DeepSeekTranslator(api_key)
        
        # Загружаем контекст книги если есть
        self.book_context = {}
        if context_file and Path(context_file).exists():
            with open(context_file, 'r', encoding='utf-8') as f:
                self.book_context = json.load(f)
        
        # Настройки адаптации
        self.adaptation_style = "professional_casual"  # Профессиональный, но доступный
        self.explanation_depth = "moderate"  # Умеренная глубина объяснений
        
    def create_audio_adaptation_prompt(self, text: str, context_before: str = "", 
                                      context_after: str = "") -> str:
        """Создает промпт для адаптации текста под аудиоформат"""
        
        # Формируем контекст книги
        book_info = ""
        if self.book_context:
            book_info = f"""
Контекст книги:
- Тема: {self.book_context.get('title', 'техническая документация')}
- Аудитория: {self.book_context.get('target_audience', 'специалисты')}
- Технический уровень: {self.book_context.get('technical_level', 'средний')}
"""
        
        prompt = f"""Адаптируй следующий технический текст для прослушивания в формате аудиокниги.

{book_info}

ЦЕЛЬ: Превратить формальный технический текст в живой профессиональный пересказ, как будто опытный эксперт объясняет материал заинтересованному коллеге за чашкой кофе.

ПРАВИЛА АДАПТАЦИИ:

1. СТРУКТУРА И ЛОГИКА:
   - Сохрани всю важную информацию и логику изложения
   - Замени сложные предложения на несколько простых
   - Добавь связующие фразы между мыслями ("Теперь давайте посмотрим...", "Важно понимать, что...")

2. ТЕРМИНЫ И АББРЕВИАТУРЫ:
   - При первом упоминании аббревиатуры расшифруй её
   - Добавь краткое пояснение для сложных терминов
   - Пример: "CMMI" → "модель CMMI — это, простыми словами, набор лучших практик для улучшения процессов"

3. СПИСКИ И ПЕРЕЧИСЛЕНИЯ:
   - Преобразуй буллет-поинты в связный рассказ
   - Используй вводные слова: "Во-первых...", "Следующий важный момент..."
   - Группируй связанные пункты

4. ССЫЛКИ И ОТСЫЛКИ:
   - Замени "см. раздел 3.2" на "об этом мы поговорим подробнее позже"
   - Убери номера таблиц/рисунков, опиши их словами
   - Замени "Figure 2.1" на "на диаграмме показано..."

5. ФОРМУЛЫ И ТЕХНИЧЕСКИЕ ДЕТАЛИ:
   - Объясни формулы словами
   - Замени символы на слова: "x > y" → "икс больше игрек"
   - Приведи простые примеры для иллюстрации

6. СТИЛЬ ИЗЛОЖЕНИЯ:
   - Используй "мы" вместо безличных конструкций
   - Добавь риторические вопросы для вовлечения
   - Включи примеры из практики где уместно
   - Используй метафоры для сложных концепций

7. АДАПТАЦИЯ ДЛЯ СЛУХА:
   - Разбей длинные абзацы на короткие смысловые блоки
   - Добавь паузы (новый абзац) после важных мыслей
   - Повтори ключевые идеи другими словами
   - Используй интонационные подсказки ("Обратите внимание...", "Это критически важно...")

КОНТЕКСТ ПРЕДЫДУЩЕГО ТЕКСТА:
{context_before[-500:] if context_before else "(начало главы)"}

ТЕКСТ ДЛЯ АДАПТАЦИИ:
{text}

КОНТЕКСТ ПОСЛЕДУЮЩЕГО ТЕКСТА:
{context_after[:500] if context_after else "(конец главы)"}

ВАЖНО:
- Сохрани профессиональный тон, но сделай его дружелюбным
- Не упрощай до примитива — аудитория понимает предметную область
- Добавь "человечности" без потери точности
- Текст должен звучать естественно при чтении вслух

Адаптированный текст:"""
        
        return prompt
    
    def create_narrator_prompt(self) -> str:
        """Создает системный промпт для роли рассказчика"""
        return """Ты — опытный технический эксперт и прекрасный рассказчик. 
Твоя задача — адаптировать технические тексты для аудиоформата, сохраняя точность и добавляя ясность.
Ты объясняешь сложные концепции доступным языком, как будто ведешь профессиональную беседу с коллегой.
Используй примеры, аналогии и связующие фразы, чтобы текст легко воспринимался на слух.
Твой стиль — профессиональный, но не сухой; информативный, но не скучный; точный, но не заумный."""
    
    def detect_problematic_elements(self, text: str) -> Dict[str, List[str]]:
        """Определяет элементы текста, требующие адаптации"""
        problems = {
            'abbreviations': [],
            'references': [],
            'lists': [],
            'formulas': [],
            'tables': [],
            'complex_sentences': []
        }
        
        # Аббревиатуры
        problems['abbreviations'] = re.findall(r'\b[A-Z]{2,}\b', text)
        
        # Ссылки
        problems['references'] = re.findall(r'(?:см\.|see|раздел|section|глава|chapter)\s+[\d.]+', text, re.IGNORECASE)
        problems['references'].extend(re.findall(r'(?:Figure|Table|Рис\.|Табл\.)\s+[\d.]+', text))
        
        # Списки (буллеты)
        if re.search(r'^\s*[•·\-*]\s+', text, re.MULTILINE):
            problems['lists'].append('bullet points detected')
        
        # Формулы и математические символы
        if re.search(r'[=<>≤≥∈∀∃∑∏∫]', text):
            problems['formulas'].append('mathematical symbols detected')
        
        # Таблицы
        if '|' in text and text.count('|') > 3:
            problems['tables'].append('table structure detected')
        
        # Сложные предложения (более 30 слов)
        sentences = text.split('.')
        for sent in sentences:
            if len(sent.split()) > 30:
                problems['complex_sentences'].append(sent[:50] + '...')
        
        return problems
    
    def adapt_paragraph_group(self, paragraphs: List[str], 
                            context_before: str = "", 
                            context_after: str = "") -> str:
        """Адаптирует группу параграфов для аудио"""
        
        # Объединяем параграфы
        text = "\n\n".join(p for p in paragraphs if p and not p.startswith('[IMAGE_'))
        
        if not text.strip():
            return ""
        
        # Создаем промпт
        prompt = self.create_audio_adaptation_prompt(text, context_before, context_after)
        system_prompt = self.create_narrator_prompt()
        
        try:
            # Отправляем на адаптацию
            adapted = self.translator.translate_text(
                prompt,
                system_message=system_prompt,
                temperature=0.7,  # Больше креативности для живого пересказа
                max_tokens=4000
            )
            
            return adapted
            
        except Exception as e:
            print(f"❌ Ошибка адаптации: {e}")
            return text  # Возвращаем оригинал в случае ошибки
    
    def adapt_chapter(self, chapter_data: Dict, chapter_num: int, 
                     paragraphs_per_group: int = 5) -> Dict:
        """Адаптирует целую главу для аудио"""
        
        adapted_chapter = {
            'title': chapter_data.get('title', ''),
            'original_paragraphs': chapter_data.get('paragraphs', []),
            'adapted_paragraphs': [],
            'adaptation_metadata': {
                'style': self.adaptation_style,
                'depth': self.explanation_depth,
                'chapter_number': chapter_num
            }
        }
        
        paragraphs = chapter_data.get('paragraphs', [])
        
        # Адаптируем заголовок
        if adapted_chapter['title']:
            adapted_title_prompt = f"""
Преобразуй заголовок главы для аудиокниги.
Добавь вступительную фразу, которая вводит слушателя в новую главу.

Оригинальный заголовок: {adapted_chapter['title']}
Номер главы: {chapter_num}

Пример результата:
"Глава третья. Процессные области CMMI. В этой главе мы подробно разберем, 
что такое процессные области и как они помогают улучшить разработку."

Адаптированный заголовок:"""
            
            try:
                adapted_chapter['title'] = self.translator.translate_text(
                    adapted_title_prompt,
                    system_message=self.create_narrator_prompt(),
                    temperature=0.5,
                    max_tokens=500
                )
            except:
                pass
        
        # Группируем и адаптируем параграфы
        for i in range(0, len(paragraphs), paragraphs_per_group):
            group = paragraphs[i:i+paragraphs_per_group]
            
            # Контекст
            context_before = "\n".join(paragraphs[max(0, i-2):i])
            context_after = "\n".join(paragraphs[i+paragraphs_per_group:i+paragraphs_per_group+2])
            
            # Адаптируем группу
            adapted = self.adapt_paragraph_group(group, context_before, context_after)
            
            if adapted:
                # Разбиваем адаптированный текст обратно на параграфы
                adapted_paras = adapted.split('\n\n')
                adapted_chapter['adapted_paragraphs'].extend(adapted_paras)
        
        return adapted_chapter
    
    def process_all_chapters(self, input_dir: str = "translations", 
                           output_dir: str = "audio_adapted",
                           workers: int = 5,
                           paragraphs_per_group: int = 5):
        """Обрабатывает все главы для адаптации"""
        
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Находим файлы глав
        chapter_files = sorted(input_path.glob("*_translated.json"))
        
        if not chapter_files:
            print(f"❌ Не найдено переведенных глав в {input_dir}")
            return
        
        print(f"📚 Найдено {len(chapter_files)} глав для адаптации")
        print(f"⚙️ Параметры:")
        print(f"   • Параграфов в группе: {paragraphs_per_group}")
        print(f"   • Параллельных потоков: {workers}")
        print(f"   • Стиль: {self.adaptation_style}")
        print()
        
        # Обрабатываем главы
        adapted_chapters = []
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {}
            
            for idx, file in enumerate(chapter_files):
                # Загружаем главу
                with open(file, 'r', encoding='utf-8') as f:
                    chapter_data = json.load(f)
                
                # Запускаем адаптацию
                future = executor.submit(self.adapt_chapter, chapter_data, idx, paragraphs_per_group)
                futures[future] = file
            
            # Обрабатываем результаты
            with tqdm(total=len(futures), desc="Адаптация глав") as pbar:
                for future in as_completed(futures):
                    file = futures[future]
                    try:
                        adapted = future.result()
                        
                        # Сохраняем адаптированную главу
                        output_file = output_path / f"{file.stem}_audio.json"
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(adapted, f, ensure_ascii=False, indent=2)
                        
                        adapted_chapters.append(adapted)
                        pbar.update(1)
                        
                    except Exception as e:
                        print(f"\n❌ Ошибка обработки {file.name}: {e}")
                        pbar.update(1)
        
        print(f"\n✅ Адаптировано {len(adapted_chapters)} глав")
        print(f"📁 Результаты сохранены в: {output_path}")
        
        return adapted_chapters


def main():
    parser = argparse.ArgumentParser(description='Адаптация текста для аудиоформата')
    parser.add_argument('--input-dir', default='translations',
                       help='Директория с переводами')
    parser.add_argument('--output-dir', default='audio_adapted',
                       help='Директория для адаптированного текста')
    parser.add_argument('--context', default='book_context.json',
                       help='Файл с контекстом книги')
    parser.add_argument('--workers', type=int, default=5,
                       help='Количество параллельных потоков')
    parser.add_argument('--group-size', type=int, default=5,
                       help='Размер группы параграфов (рекомендуется 5-7)')
    parser.add_argument('--api-key', help='DeepSeek API ключ')
    parser.add_argument('--test', action='store_true',
                       help='Тестовый режим - обработать только первую главу')
    
    args = parser.parse_args()
    
    print("🎙️ Адаптация текста для аудиокниги v2.0")
    print("=" * 60)
    print()
    print("🎯 Цель: превратить технический текст в живой пересказ")
    print("📝 Стиль: профессиональный эксперт объясняет коллеге")
    print()
    
    # Получаем API ключ
    api_key = args.api_key or os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ API ключ не найден!")
        print("   Установите DEEPSEEK_API_KEY или используйте --api-key")
        return
    
    # Создаем адаптер
    adapter = AudioTextAdapter(api_key, args.context)
    
    if args.test:
        print("🧪 ТЕСТОВЫЙ РЕЖИМ - обработка первой главы")
        
        # Тестируем на одной главе
        test_files = list(Path(args.input_dir).glob("*_translated.json"))[:1]
        if test_files:
            with open(test_files[0], 'r', encoding='utf-8') as f:
                chapter = json.load(f)
            
            # Берем первые несколько параграфов
            test_paragraphs = chapter.get('paragraphs', [])[:3]
            
            print("\n📄 Оригинальный текст:")
            print("-" * 40)
            for p in test_paragraphs:
                if p and not p.startswith('[IMAGE_'):
                    print(p[:200] + "..." if len(p) > 200 else p)
                    print()
            
            print("\n🔄 Адаптация...")
            adapted = adapter.adapt_paragraph_group(test_paragraphs)
            
            print("\n🎙️ Адаптированный текст:")
            print("-" * 40)
            print(adapted)
            
            # Анализ проблемных элементов
            problems = adapter.detect_problematic_elements("\n".join(test_paragraphs))
            print("\n📊 Обнаруженные элементы для адаптации:")
            for problem_type, items in problems.items():
                if items:
                    print(f"   • {problem_type}: {len(items)} элементов")
    else:
        # Полная обработка
        adapter.process_all_chapters(
            args.input_dir,
            args.output_dir,
            args.workers,
            args.group_size
        )
        
        print("\n✅ Готово!")
        print("\n💡 Теперь можно создать аудиокнигу из адаптированного текста:")
        print(f"   python3 05_create_audiobook.py --translations-dir {args.output_dir}")


if __name__ == "__main__":
    main()