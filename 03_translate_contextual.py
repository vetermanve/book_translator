#!/usr/bin/env python3
"""
Улучшенный переводчик с контекстом между параграфами
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import time
from tqdm import tqdm

from deepseek_translator import DeepSeekTranslator
from translation_manager import TranslationProgress, ContextManager


class ContextualTranslator:
    """Переводчик с передачей контекста между параграфами"""
    
    def __init__(self, source_dir="extracted_proper", translations_dir="translations"):
        self.source_dir = Path(source_dir)
        self.translations_dir = Path(translations_dir)
        self.translations_dir.mkdir(exist_ok=True)
        
        self.translator = DeepSeekTranslator()
        self.progress = TranslationProgress()
        self.context_manager = ContextManager()
        
        # Контекст перевода - накапливается по мере перевода
        self.rolling_context = {
            'glossary': {},  # Накапливаемый глоссарий терминов
            'recent_translations': [],  # Последние N переведенных параграфов
            'chapter_summary': '',  # Резюме текущей главы
            'previous_paragraph': '',  # Предыдущий параграф для связности
        }
        
    def translate_book(self):
        """Переводит всю книгу с контекстом"""
        
        # Загружаем список глав
        chapters = self._load_chapters()
        if not chapters:
            print("❌ Главы не найдены!")
            return
        
        print(f"📚 Найдено {len(chapters)} глав для перевода")
        
        # Переводим каждую главу
        for chapter_file in tqdm(chapters, desc="Перевод глав"):
            chapter_num = self._extract_chapter_num(chapter_file)
            
            # Проверяем, не переведена ли уже глава
            if self.progress.is_chapter_translated(chapter_num):
                print(f"✅ Глава {chapter_num} уже переведена, пропускаем")
                # Загружаем контекст из переведенной главы
                self._load_chapter_context(chapter_num)
                continue
            
            print(f"\n📖 Перевод главы {chapter_num}...")
            self._translate_chapter(chapter_file)
        
        print("\n✨ Перевод завершен!")
    
    def _translate_chapter(self, chapter_file):
        """Переводит одну главу с контекстом"""
        
        # Загружаем данные главы
        with open(chapter_file, 'r', encoding='utf-8') as f:
            chapter_data = json.load(f)
        
        chapter_num = chapter_data['number']
        
        # Загружаем контекст главы из файлов контекста
        try:
            chapter_context = self.context_manager.load_chapter_context(chapter_num)
        except:
            # Если контекст не найден, создаем пустой
            chapter_context = {}
        
        # Обновляем rolling context
        if chapter_context:
            self.rolling_context['chapter_summary'] = chapter_context.get('summary', '')
        
        # Переводим заголовок
        translated_title = self._translate_title(chapter_data['title'])
        
        # Переводим параграфы с передачей контекста
        translated_paragraphs = []
        total_paragraphs = len(chapter_data['paragraphs'])
        
        print(f"📝 Переводим {total_paragraphs} параграфов...")
        
        for idx, paragraph in enumerate(tqdm(chapter_data['paragraphs'], desc="Параграфы")):
            
            # Пропускаем изображения
            if paragraph.startswith("[IMAGE_"):
                translated_paragraphs.append(paragraph)
                continue
            
            # Переводим параграф с контекстом
            translated = self._translate_paragraph_with_context(
                paragraph, 
                idx, 
                total_paragraphs,
                chapter_context
            )
            
            translated_paragraphs.append(translated)
            
            # Обновляем контекст
            self._update_rolling_context(paragraph, translated)
            
            # Небольшая задержка для избежания перегрузки API
            if idx % 10 == 0 and idx > 0:
                time.sleep(0.5)
        
        # Генерируем резюме главы
        summary = self._generate_chapter_summary(translated_paragraphs)
        
        # Сохраняем перевод
        translation = {
            "number": chapter_num,
            "title": translated_title,
            "paragraphs": translated_paragraphs,
            "summary": summary,
            "original_word_count": chapter_data.get('word_count', 0),
            "translator": "Contextual DeepSeek",
            "translation_date": datetime.now().isoformat()
        }
        
        output_file = self.translations_dir / f"chapter_{chapter_num:03d}_translated.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(translation, f, ensure_ascii=False, indent=2)
        
        # Отмечаем главу как завершенную
        self.progress.mark_chapter_complete(chapter_num)
        
        print(f"✅ Глава {chapter_num} переведена!")
    
    def _translate_paragraph_with_context(self, paragraph, idx, total, chapter_context):
        """Переводит параграф с учетом контекста"""
        
        # Формируем контекст для перевода
        context_prompt = self._build_context_prompt(idx, total, chapter_context)
        
        # Формируем промпт для перевода
        prompt = f"""{context_prompt}

Переведи следующий параграф, учитывая контекст:

{paragraph}

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Сохраняй связность с предыдущим текстом
2. Используй установленную терминологию из глоссария
3. Сохраняй стиль и тон документа
4. НЕ добавляй объяснения или комментарии
5. Возвращай ТОЛЬКО перевод

Перевод:"""
        
        try:
            response = self.translator.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3,
            )
            
            translated = response.choices[0].message.content.strip()
            
            # Очистка от возможных артефактов
            translated = self._clean_translation(translated)
            
            return translated
            
        except Exception as e:
            print(f"⚠️ Ошибка при переводе параграфа {idx}: {e}")
            # Fallback на простой перевод
            return self.translator._fallback_translate(paragraph)
    
    def _build_context_prompt(self, idx, total, chapter_context):
        """Строит контекстный промпт для перевода"""
        
        context_parts = []
        
        # Позиция в главе
        position = "начале" if idx < total * 0.3 else "середине" if idx < total * 0.7 else "конце"
        context_parts.append(f"Позиция в главе: {position} ({idx+1}/{total})")
        
        # Предыдущий параграф для связности
        if self.rolling_context['previous_paragraph']:
            context_parts.append(f"Предыдущий параграф: ...{self.rolling_context['previous_paragraph'][-200:]}")
        
        # Глоссарий накопленных терминов
        if self.rolling_context['glossary']:
            terms = list(self.rolling_context['glossary'].items())[:20]  # Топ-20 терминов
            terms_str = ", ".join([f"{en}: {ru}" for en, ru in terms])
            context_parts.append(f"Используемые термины: {terms_str}")
        
        # Контекст главы
        if chapter_context:
            if 'key_concepts' in chapter_context:
                context_parts.append(f"Ключевые концепции главы: {', '.join(chapter_context['key_concepts'][:5])}")
            if 'summary' in chapter_context:
                context_parts.append(f"О чем глава: {chapter_context['summary'][:200]}")
        
        return "\n".join(context_parts)
    
    def _update_rolling_context(self, original, translated):
        """Обновляет накапливаемый контекст"""
        
        # Сохраняем предыдущий параграф
        self.rolling_context['previous_paragraph'] = translated
        
        # Добавляем в историю переводов (храним последние 5)
        self.rolling_context['recent_translations'].append(translated)
        if len(self.rolling_context['recent_translations']) > 5:
            self.rolling_context['recent_translations'].pop(0)
        
        # Извлекаем и обновляем термины
        self._extract_and_update_terms(original, translated)
    
    def _extract_and_update_terms(self, original, translated):
        """Извлекает термины из перевода и обновляет глоссарий"""
        
        # Простая эвристика: ищем слова с заглавной буквы (кроме начала предложения)
        import re
        
        # Английские термины
        en_terms = re.findall(r'(?<![.!?]\s)\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', original)
        
        # Русские термины (предполагаем соответствие по позиции)
        ru_terms = re.findall(r'(?<![.!?]\s)\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*\b', translated)
        
        # Обновляем глоссарий (простое соответствие)
        for en_term in en_terms[:3]:  # Берем первые 3 термина
            if en_term not in self.rolling_context['glossary'] and en_term not in ['The', 'This', 'That']:
                # Пытаемся найти соответствие в русском тексте
                for ru_term in ru_terms:
                    if len(ru_term) > 3:  # Фильтруем короткие слова
                        self.rolling_context['glossary'][en_term] = ru_term
                        break
    
    def _translate_title(self, title):
        """Переводит заголовок главы"""
        
        prompt = f"""Переведи заголовок главы технической документации:

{title}

Требования:
- Сохрани официальный стиль
- Используй принятую терминологию
- Будь лаконичным

Перевод:"""
        
        try:
            response = self.translator.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️ Ошибка при переводе заголовка: {e}")
            return self.translator._fallback_translate(title)
    
    def _generate_chapter_summary(self, paragraphs):
        """Генерирует краткое резюме главы"""
        
        # Берем первые и последние параграфы для резюме
        sample_text = []
        
        # Первые 3 параграфа
        for p in paragraphs[:3]:
            if not p.startswith("[IMAGE_"):
                sample_text.append(p)
        
        # Последние 2 параграфа
        for p in paragraphs[-2:]:
            if not p.startswith("[IMAGE_"):
                sample_text.append(p)
        
        if not sample_text:
            return "Глава содержит преимущественно изображения"
        
        text_for_summary = "\n".join(sample_text[:5])  # Максимум 5 параграфов
        
        prompt = f"""На основе следующих фрагментов создай краткое резюме главы (1-2 предложения):

{text_for_summary[:1500]}

Резюме:"""
        
        try:
            response = self.translator.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Ты создаешь краткие резюме технических глав."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.5,
            )
            
            return response.choices[0].message.content.strip()
            
        except:
            return "Резюме недоступно"
    
    def _get_system_prompt(self):
        """Системный промпт для переводчика"""
        return """Ты профессиональный переводчик технической документации CMMI.
        
Твоя задача - создавать точные, читаемые переводы с английского на русский.

Ключевые принципы:
1. Сохраняй техническую точность
2. Используй принятую русскоязычную терминологию
3. Обеспечивай связность текста
4. Адаптируй для русскоязычной аудитории
5. Сохраняй форматирование и структуру

Стиль: формальный, технический, профессиональный."""
    
    def _clean_translation(self, text):
        """Очищает перевод от артефактов"""
        
        # Убираем возможные маркеры
        text = text.replace("Перевод:", "").strip()
        text = text.replace("Translation:", "").strip()
        
        # Убираем кавычки если весь текст в них
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        
        return text.strip()
    
    def _load_chapters(self):
        """Загружает список файлов глав"""
        
        chapters = sorted(self.source_dir.glob("chapter_*.json"))
        return chapters
    
    def _extract_chapter_num(self, filepath):
        """Извлекает номер главы из имени файла"""
        
        import re
        match = re.search(r'chapter_(\d+)', filepath.name)
        if match:
            return int(match.group(1))
        return 0
    
    def _load_chapter_context(self, chapter_num):
        """Загружает контекст из уже переведенной главы"""
        
        trans_file = self.translations_dir / f"chapter_{chapter_num:03d}_translated.json"
        if trans_file.exists():
            with open(trans_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Обновляем глоссарий из переведенной главы
                # Здесь можно добавить более сложную логику извлечения терминов
                if 'summary' in data:
                    self.rolling_context['chapter_summary'] = data['summary']


def main():
    """Основная функция"""
    
    print("🚀 Запуск контекстного переводчика CMMI...")
    print("=" * 50)
    
    translator = ContextualTranslator()
    
    try:
        translator.translate_book()
        print("\n✅ Перевод успешно завершен!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Перевод прерван пользователем")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()