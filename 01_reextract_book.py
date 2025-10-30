#!/usr/bin/env python3
"""
Переэкстрактор PDF с правильной разбивкой на параграфы
"""

import fitz
import os
import json
import re
from pathlib import Path
from tqdm import tqdm
import hashlib


class ProperPDFExtractor:
    """Экстрактор PDF с правильной разбивкой на параграфы"""
    
    def __init__(self, pdf_path, output_dir="extracted_fixed"):
        self.pdf_path = pdf_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.metadata = {
            "total_pages": 0,
            "chapters": [],
            "extraction_complete": False,
            "book_title": "",
            "book_info": {}
        }
        
    def extract_all(self):
        """Извлечение всего содержимого из PDF с правильной разбивкой"""
        print("📖 Открываем PDF документ...")
        doc = fitz.open(self.pdf_path)
        self.metadata["total_pages"] = len(doc)
        
        # Извлекаем метаданные книги
        self._extract_book_metadata(doc)
        
        # Получаем оглавление
        toc = doc.get_toc()
        
        all_pages = []
        print("📄 Извлекаем текст с сохранением форматирования...")
        for page_num in tqdm(range(len(doc)), desc="Чтение страниц"):
            page = doc[page_num]
            # Получаем текст с сохранением структуры
            text = page.get_text()
            all_pages.append({
                'page_num': page_num,
                'text': text
            })
        
        # Определяем структуру глав
        if toc and len(toc) > 0:
            print("📚 Используем оглавление для создания глав...")
            chapters_data = self._smart_split_by_toc(all_pages, toc, doc)
        else:
            print("📊 Разбиваем на главы по 30 страниц...")
            chapters_data = self._split_by_pages(all_pages, 30)
        
        # Сохраняем главы
        print("💾 Сохраняем главы с правильными параграфами...")
        chapter_number = 0
        for chapter_data in tqdm(chapters_data, desc="Сохранение глав"):
            self._save_chapter(
                chapter_data["title"], 
                chapter_data["pages"], 
                chapter_number,
                chapter_data.get("start_page", 0),
                chapter_data.get("end_page", 0)
            )
            
            self.metadata["chapters"].append({
                "number": chapter_number,
                "title": chapter_data["title"],
                "start_page": chapter_data.get("start_page", 0),
                "end_page": chapter_data.get("end_page", 0),
                "page_count": chapter_data.get("end_page", 0) - chapter_data.get("start_page", 0) + 1,
                "status": "extracted"
            })
            
            chapter_number += 1
        
        doc.close()
        
        self.metadata["extraction_complete"] = True
        self._save_metadata()
        
        print(f"\n✅ Извлечение завершено!")
        print(f"   📑 Глав: {len(self.metadata['chapters'])}")
        print(f"   📄 Страниц: {self.metadata['total_pages']}")
        
        return self.metadata
    
    def _smart_split_by_toc(self, all_pages, toc, doc):
        """Умная разбивка на главы по оглавлению"""
        chapters = []
        
        # Фильтруем TOC - оставляем только главы верхнего уровня и важные разделы
        filtered_toc = []
        
        for i, entry in enumerate(toc):
            level, title, page_num = entry
            
            # Конвертируем номер страницы PDF в индекс Python (PDF начинается с 1)
            page_index = page_num - 1
            
            # Оставляем элементы уровня 0-2 для большей детализации
            if level <= 2 or any(keyword in title.lower() for keyword in 
                                ['chapter', 'part', 'introduction', 'глава', 'часть', 'appendix', 
                                 'process area', 'section']):
                filtered_toc.append((level, title, page_index))
        
        # Объединяем мелкие разделы
        MIN_PAGES = 2  # Минимальный размер главы
        merged_toc = []
        
        i = 0
        while i < len(filtered_toc):
            current_level, current_title, current_page = filtered_toc[i]
            
            # Определяем конец текущей главы
            if i + 1 < len(filtered_toc):
                next_page = filtered_toc[i + 1][2]
            else:
                next_page = len(all_pages) - 1
            
            # Если глава слишком маленькая, объединяем с следующими
            accumulated_title = current_title
            accumulated_start = current_page
            accumulated_end = next_page
            
            # Объединяем маленькие главы
            while accumulated_end - accumulated_start < MIN_PAGES and i + 1 < len(filtered_toc):
                i += 1
                if i < len(filtered_toc):
                    # Обновляем конец
                    if i + 1 < len(filtered_toc):
                        accumulated_end = filtered_toc[i + 1][2]
                    else:
                        accumulated_end = len(all_pages) - 1
                    
                    # Если это раздел того же уровня, обновляем название
                    if filtered_toc[i][0] <= current_level + 1:
                        if len(accumulated_title) < 100:
                            accumulated_title += f" / {filtered_toc[i][1]}"
            
            merged_toc.append((current_level, accumulated_title, accumulated_start, accumulated_end))
            i += 1
        
        # Создаем главы
        for i, (level, title, start_page, end_page) in enumerate(merged_toc):
            # Убеждаемся, что нет перекрытий
            if i > 0 and start_page <= merged_toc[i-1][3]:
                start_page = merged_toc[i-1][3] + 1
            
            # Собираем страницы главы
            chapter_pages = all_pages[start_page:end_page+1]
            
            chapters.append({
                "title": title,
                "pages": chapter_pages,
                "start_page": start_page,
                "end_page": end_page
            })
        
        return chapters
    
    def _split_by_pages(self, all_pages, pages_per_chapter):
        """Разбиение на главы по количеству страниц"""
        chapters = []
        
        for i in range(0, len(all_pages), pages_per_chapter):
            chapter_pages = all_pages[i:i + pages_per_chapter]
            
            # Генерируем название
            title = f"Часть {i // pages_per_chapter + 1}"
            
            chapters.append({
                "title": title,
                "pages": chapter_pages,
                "start_page": i,
                "end_page": min(i + pages_per_chapter - 1, len(all_pages) - 1)
            })
        
        return chapters
    
    def _save_chapter(self, title, pages, chapter_num, start_page, end_page):
        """Сохранение главы в JSON с правильной разбивкой на параграфы"""
        filename = f"chapter_{chapter_num:03d}.json"
        filepath = self.output_dir / filename
        
        # Объединяем текст всех страниц
        full_text = '\n'.join([p['text'] for p in pages])
        
        # НЕ очищаем текст агрессивно - сохраняем структуру
        # Только убираем избыточные пустые строки
        full_text = re.sub(r'\n{4,}', '\n\n\n', full_text)
        
        # Разбиваем на параграфы правильно
        paragraphs = self._split_into_proper_paragraphs(full_text)
        
        chapter_data = {
            "number": chapter_num,
            "title": title,
            "start_page": start_page,
            "end_page": end_page,
            "paragraphs": paragraphs,
            "word_count": len(full_text.split())
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=2)
    
    def _split_into_proper_paragraphs(self, text):
        """Умная разбивка текста на параграфы с сохранением структуры"""
        paragraphs = []
        current_paragraph = []
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Пустая строка - возможный конец параграфа
            if not stripped:
                if current_paragraph:
                    # Объединяем строки текущего параграфа
                    para_text = ' '.join(current_paragraph)
                    # Фильтруем только очень короткие фрагменты
                    if len(para_text) > 20:  # Минимум 20 символов
                        paragraphs.append(para_text)
                    current_paragraph = []
            else:
                # Признаки начала нового параграфа:
                # - Строка начинается с большой буквы после точки
                # - Строка начинается с номера (нумерованный список)
                # - Строка начинается с буллита
                # - Предыдущая строка заканчивалась точкой/вопросом/восклицанием
                
                if current_paragraph and self._is_new_paragraph(current_paragraph[-1], stripped):
                    # Сохраняем текущий параграф
                    para_text = ' '.join(current_paragraph)
                    if len(para_text) > 20:
                        paragraphs.append(para_text)
                    current_paragraph = [stripped]
                else:
                    # Продолжаем текущий параграф
                    current_paragraph.append(stripped)
        
        # Добавляем последний параграф
        if current_paragraph:
            para_text = ' '.join(current_paragraph)
            if len(para_text) > 20:
                paragraphs.append(para_text)
        
        return paragraphs
    
    def _is_new_paragraph(self, prev_line, curr_line):
        """Определяет, начинается ли новый параграф"""
        # Если предыдущая строка закончилась точкой/вопросом/восклицанием
        if prev_line.rstrip().endswith(('.', '!', '?', ':', ';')):
            # И текущая начинается с большой буквы или цифры
            if curr_line and (curr_line[0].isupper() or curr_line[0].isdigit()):
                return True
        
        # Если строка начинается с маркера списка
        list_markers = ['•', '●', '○', '■', '□', '▪', '▫', '-', '*', '–']
        if any(curr_line.startswith(marker) for marker in list_markers):
            return True
        
        # Если строка начинается с номера пункта
        if re.match(r'^\d+[.)]\s', curr_line):
            return True
        
        # Если строка начинается с буквенного пункта
        if re.match(r'^[a-zA-Z][.)]\s', curr_line):
            return True
        
        return False
    
    def _extract_book_metadata(self, doc):
        """Извлечение метаданных книги"""
        metadata = doc.metadata
        if metadata:
            self.metadata["book_info"] = {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "keywords": metadata.get("keywords", ""),
            }
    
    def _save_metadata(self):
        """Сохранение метаданных"""
        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("🚀 Запуск переэкстракции PDF с правильной структурой...")
    
    extractor = ProperPDFExtractor("book.pdf")
    metadata = extractor.extract_all()
    
    print("\n📊 Статистика экстракции:")
    print(f"   Всего глав: {len(metadata['chapters'])}")
    print(f"   Всего страниц: {metadata['total_pages']}")
    
    # Проверка первой главы
    first_chapter = Path("extracted_proper/chapter_000.json")
    if first_chapter.exists():
        with open(first_chapter, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"\n📝 Пример главы '{data['title']}':")
            print(f"   Параграфов: {len(data['paragraphs'])}")
            print(f"   Слов: {data['word_count']}")
            if data['paragraphs']:
                print(f"   Первый параграф: {data['paragraphs'][0][:100]}...")