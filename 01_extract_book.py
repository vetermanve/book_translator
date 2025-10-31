#!/usr/bin/env python3
"""
Оптимизированный экстрактор книг с агрессивным разбиением на короткие параграфы
для лучшего качества перевода
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Optional
import sys

class OptimizedBookExtractor:
    def __init__(self, book_file="book.txt", output_dir="extracted"):
        self.book_file = Path(book_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Параметры для разбиения параграфов
        self.max_words_per_paragraph = 75   # Максимум слов в параграфе
        self.ideal_words_per_paragraph = 50  # Идеальный размер параграфа
        
    def extract(self) -> bool:
        """Основной метод извлечения"""
        if not self.book_file.exists():
            print(f"❌ Файл {self.book_file} не найден!")
            return False
        
        with open(self.book_file, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        print(f"📖 Загружен текст: {len(full_text)} символов")
        
        # Извлекаем главы
        chapters = self._detect_text_chapters(full_text)
        
        if not chapters:
            print("⚠️ Не удалось определить структуру глав, используем весь текст")
            chapters = [{'title': 'Full Book', 'text': full_text}]
        
        print(f"📚 Найдено глав: {len(chapters)}")
        
        # Обрабатываем каждую главу
        total_words = 0
        chapter_list = []
        
        for i, chapter in enumerate(chapters):
            # Агрессивное разбиение на параграфы
            paragraphs = self._smart_split_paragraphs(chapter['text'])
            
            # Фильтруем пустые параграфы
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
            
            word_count = sum(len(p.split()) for p in paragraphs)
            total_words += word_count
            
            # Формируем данные главы
            chapter_data = {
                'number': i,
                'title': chapter['title'],
                'paragraphs': paragraphs,
                'paragraph_count': len(paragraphs),
                'word_count': word_count,
                'char_count': len(chapter['text']),
                'source_format': 'txt',
                'extraction_method': 'optimized_smart_split'
            }
            
            # Сохраняем
            chapter_file = self.output_dir / f"chapter_{i:03d}.json"
            with open(chapter_file, 'w', encoding='utf-8') as f:
                json.dump(chapter_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Глава {i}: {chapter['title']}")
            print(f"   Параграфов: {len(paragraphs)}")
            print(f"   Слов: {word_count}")
            
            # Показываем статистику размеров параграфов
            para_sizes = [len(p.split()) for p in paragraphs]
            if para_sizes:
                avg_size = sum(para_sizes) / len(para_sizes)
                print(f"   Средний размер параграфа: {avg_size:.0f} слов")
                print(f"   Макс/Мин: {max(para_sizes)}/{min(para_sizes)} слов")
            
            chapter_list.append({
                'number': i,
                'title': chapter['title'],
                'paragraph_count': len(paragraphs),
                'word_count': word_count
            })
        
        # Сохраняем метаданные
        metadata = {
            'total_chapters': len(chapters),
            'total_words': total_words,
            'chapters': chapter_list,
            'extraction_method': 'optimized_smart_split',
            'max_words_per_paragraph': self.max_words_per_paragraph,
            'ideal_words_per_paragraph': self.ideal_words_per_paragraph
        }
        
        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"\n📊 Всего извлечено {total_words} слов")
        return True
    
    def _smart_split_paragraphs(self, text: str) -> List[str]:
        """
        Умное разбиение текста на короткие параграфы
        
        Стратегия:
        1. Сначала разбиваем по двойным переносам (естественные параграфы)
        2. Затем длинные параграфы разбиваем по точкам на группы предложений
        3. Очень длинные предложения можно разбить по точкам с запятой или двоеточиям
        """
        # Заменяем плейсхолдеры изображений на специальные маркеры
        text = re.sub(r'\[IMAGE[_ ]\d+\]', '<IMAGE_PLACEHOLDER>', text)
        
        # Разбиваем на естественные параграфы
        natural_paragraphs = re.split(r'\n\s*\n', text)
        
        result_paragraphs = []
        
        for para in natural_paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Проверяем, не является ли это плейсхолдером
            if '<IMAGE_PLACEHOLDER>' in para:
                # Восстанавливаем оригинальный плейсхолдер
                para = re.sub(r'<IMAGE_PLACEHOLDER>', '[IMAGE_001]', para)
                result_paragraphs.append(para)
                continue
            
            # Считаем слова
            words = len(para.split())
            
            if words <= self.max_words_per_paragraph:
                # Параграф уже достаточно короткий
                result_paragraphs.append(para)
            else:
                # Нужно разбить на более короткие фрагменты
                sub_paragraphs = self._split_long_paragraph(para)
                result_paragraphs.extend(sub_paragraphs)
        
        return result_paragraphs
    
    def _split_long_paragraph(self, para: str) -> List[str]:
        """
        Разбивает длинный параграф на короткие фрагменты
        """
        # Разбиваем по предложениям (по точкам, ! и ?)
        # Но сохраняем сокращения типа Dr., Mr., etc.
        sentences = self._split_into_sentences(para)
        
        if not sentences:
            return [para]
        
        # Группируем предложения в параграфы оптимального размера
        result = []
        current_group = []
        current_words = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_words = len(sentence.split())
            
            # Если одно предложение слишком длинное, пробуем разбить его дальше
            if sentence_words > self.max_words_per_paragraph:
                # Сохраняем текущую группу
                if current_group:
                    result.append(' '.join(current_group))
                    current_group = []
                    current_words = 0
                
                # Разбиваем длинное предложение
                sub_parts = self._split_very_long_sentence(sentence)
                result.extend(sub_parts)
                continue
            
            # Решаем, добавить ли предложение в текущую группу
            if current_words + sentence_words > self.max_words_per_paragraph:
                # Но если текущая группа слишком маленькая, добавляем все равно
                if current_words < 30 and sentence_words < self.ideal_words_per_paragraph:
                    current_group.append(sentence)
                    current_words += sentence_words
                else:
                    # Сохраняем текущую группу и начинаем новую
                    if current_group:
                        result.append(' '.join(current_group))
                    current_group = [sentence]
                    current_words = sentence_words
            else:
                # Добавляем к текущей группе
                current_group.append(sentence)
                current_words += sentence_words
                
                # Если достигли идеального размера, завершаем группу
                if current_words >= self.ideal_words_per_paragraph:
                    result.append(' '.join(current_group))
                    current_group = []
                    current_words = 0
        
        # Добавляем остаток
        if current_group:
            result.append(' '.join(current_group))
        
        return result
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Разбивает текст на предложения
        """
        # Защищаем сокращения
        text = re.sub(r'Dr\.', 'Dr<DOT>', text)
        text = re.sub(r'Mr\.', 'Mr<DOT>', text)
        text = re.sub(r'Mrs\.', 'Mrs<DOT>', text)
        text = re.sub(r'Ms\.', 'Ms<DOT>', text)
        text = re.sub(r'Prof\.', 'Prof<DOT>', text)
        text = re.sub(r'Sr\.', 'Sr<DOT>', text)
        text = re.sub(r'Jr\.', 'Jr<DOT>', text)
        text = re.sub(r'Ph\.D', 'Ph<DOT>D', text)
        text = re.sub(r'M\.D', 'M<DOT>D', text)
        text = re.sub(r'B\.A', 'B<DOT>A', text)
        text = re.sub(r'M\.A', 'M<DOT>A', text)
        text = re.sub(r'B\.S', 'B<DOT>S', text)
        text = re.sub(r'Ph\.D\.', 'Ph<DOT>D<DOT>', text)
        text = re.sub(r'i\.e\.', 'i<DOT>e<DOT>', text)
        text = re.sub(r'e\.g\.', 'e<DOT>g<DOT>', text)
        text = re.sub(r'etc\.', 'etc<DOT>', text)
        text = re.sub(r'vs\.', 'vs<DOT>', text)
        text = re.sub(r'U\.S\.', 'U<DOT>S<DOT>', text)
        text = re.sub(r'U\.K\.', 'U<DOT>K<DOT>', text)
        
        # Разбиваем по точкам, ! и ?
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Восстанавливаем точки в сокращениях
        sentences = [s.replace('<DOT>', '.') for s in sentences]
        
        return sentences
    
    def _split_very_long_sentence(self, sentence: str) -> List[str]:
        """
        Разбивает очень длинное предложение на части
        """
        # Пробуем разбить по точке с запятой
        parts = sentence.split(';')
        if len(parts) > 1:
            result = []
            for part in parts:
                part = part.strip()
                if part:
                    # Добавляем точку с запятой обратно
                    if part != parts[-1].strip():
                        part += ';'
                    result.append(part)
            return result
        
        # Пробуем разбить по двоеточию
        parts = sentence.split(':')
        if len(parts) > 1:
            result = []
            for i, part in enumerate(parts):
                part = part.strip()
                if part:
                    # Добавляем двоеточие к первой части
                    if i == 0:
                        part += ':'
                    result.append(part)
            return result
        
        # Пробуем разбить по длинным спискам с запятыми
        if sentence.count(',') > 3:
            # Ищем позицию для разбиения примерно посередине
            words = sentence.split()
            mid_point = len(words) // 2
            
            # Ищем ближайшую запятую к середине
            current_pos = 0
            best_split = -1
            for i, word in enumerate(words):
                if ',' in word and abs(i - mid_point) < abs(best_split - mid_point):
                    best_split = i
            
            if best_split > 0:
                part1 = ' '.join(words[:best_split + 1])
                part2 = ' '.join(words[best_split + 1:])
                return [part1, part2]
        
        # Если ничего не получилось, возвращаем как есть
        return [sentence]
    
    def _detect_text_chapters(self, text: str) -> List[Dict]:
        """
        Определяет главы в тексте
        """
        chapters = []
        
        # Паттерны для поиска глав
        patterns = [
            r'Chapter\s+(\d+)',
            r'CHAPTER\s+(\d+)',
            r'Chapter\s+([IVX]+)',
            r'Part\s+(\d+)',
            r'Section\s+(\d+)',
            r'^\s*(\d+)\s*\n',
            r'^\s*([IVX]+)\s*\n'
        ]
        
        # Ищем все совпадения
        positions = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                positions.append((match.start(), match.group(0), match.group(1)))
        
        # Сортируем по позиции
        positions.sort(key=lambda x: x[0])
        
        # Удаляем дубликаты близких позиций
        filtered_positions = []
        last_pos = -1000
        for pos, full_match, chapter_num in positions:
            if pos - last_pos > 50:
                filtered_positions.append((pos, full_match, chapter_num))
                last_pos = pos
        
        # Проверяем, есть ли текст до первой главы (введение)
        if filtered_positions and filtered_positions[0][0] > 100:
            intro_text = text[:filtered_positions[0][0]].strip()
            if intro_text:
                chapters.append({
                    'title': 'Введение',
                    'text': intro_text
                })
        
        # Извлекаем главы
        for i, (pos, full_match, chapter_num) in enumerate(filtered_positions):
            # Определяем конец главы
            if i < len(filtered_positions) - 1:
                end_pos = filtered_positions[i + 1][0]
            else:
                end_pos = len(text)
            
            chapter_text = text[pos:end_pos].strip()
            
            # Убираем заголовок главы из текста
            chapter_text = chapter_text.replace(full_match, '', 1).strip()
            
            # Проверяем первые слова для определения названия
            first_words = chapter_text[:100].split()[:10]
            title_candidate = ' '.join(first_words[:5])
            
            # Если есть явный заголовок (короткая строка в начале)
            lines = chapter_text.split('\n', 2)
            if len(lines) > 0 and len(lines[0]) < 100 and len(lines[0].split()) < 10:
                chapter_title = lines[0].strip()
                chapter_text = '\n'.join(lines[1:]) if len(lines) > 1 else ''
            else:
                chapter_title = f"Глава {chapter_num}"
            
            chapters.append({
                'title': chapter_title,
                'text': chapter_text
            })
        
        # Если главы не найдены, но текст есть
        if not chapters and text.strip():
            chapters.append({
                'title': 'Полный текст',
                'text': text
            })
        
        return chapters

def main():
    print("📚 Оптимизированный экстрактор книг v2.0")
    print("=" * 50)
    
    extractor = OptimizedBookExtractor()
    
    if extractor.extract():
        print("\n✅ Извлечение завершено успешно!")
    else:
        print("\n❌ Ошибка при извлечении")
        sys.exit(1)

if __name__ == "__main__":
    main()