#!/usr/bin/env python3

import fitz
import os
import json
import re
from pathlib import Path
from tqdm import tqdm
import hashlib


class FixedPDFExtractor:
    """Исправленный экстрактор PDF с правильной разбивкой на главы"""
    
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
        
        all_text = []
        print("📄 Извлекаем текст...")
        for page_num in tqdm(range(len(doc)), desc="Чтение страниц"):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(text)
        
        # Определяем структуру глав
        if toc and len(toc) > 0:
            print("📚 Используем оглавление для создания глав...")
            chapters_data = self._smart_split_by_toc(all_text, toc, doc)
        else:
            print("📊 Разбиваем на главы по 30 страниц...")
            chapters_data = self._split_by_pages(all_text, 30)
        
        # Сохраняем главы
        print("💾 Сохраняем главы...")
        chapter_number = 0
        for chapter_data in tqdm(chapters_data, desc="Сохранение глав"):
            self._save_chapter(
                chapter_data["title"], 
                chapter_data["text"], 
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
        
        # Проверка целостности
        self._verify_extraction()
        
        return self.metadata
    
    def _smart_split_by_toc(self, all_text, toc, doc):
        """Умная разбивка на главы по оглавлению без перекрытий"""
        chapters = []
        
        # Фильтруем TOC - оставляем только главы верхнего уровня и важные разделы
        filtered_toc = []
        
        for i, entry in enumerate(toc):
            level, title, page_num = entry
            
            # Конвертируем номер страницы PDF в индекс Python (PDF начинается с 1)
            page_index = page_num - 1
            
            # Оставляем элементы уровня 0-2 для большей детализации
            # или элементы с ключевыми словами
            if level <= 2 or any(keyword in title.lower() for keyword in 
                                ['chapter', 'part', 'introduction', 'глава', 'часть', 'appendix', 
                                 'process area', 'section']):
                filtered_toc.append((level, title, page_index))
        
        # Объединяем мелкие разделы
        MIN_PAGES = 2  # Минимальный размер главы (уменьшаем для большей детализации)
        merged_toc = []
        
        i = 0
        while i < len(filtered_toc):
            current_level, current_title, current_page = filtered_toc[i]
            
            # Определяем конец текущей главы
            if i + 1 < len(filtered_toc):
                next_page = filtered_toc[i + 1][2]
            else:
                next_page = len(all_text) - 1
            
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
                        accumulated_end = len(all_text) - 1
                    
                    # Если это раздел того же уровня, обновляем название
                    if filtered_toc[i][0] <= current_level + 1:
                        if len(accumulated_title) < 100:
                            accumulated_title += f" / {filtered_toc[i][1]}"
            
            merged_toc.append((current_level, accumulated_title, accumulated_start, accumulated_end))
            i += 1
        
        # Создаем главы без перекрытий
        for i, (level, title, start_page, end_page) in enumerate(merged_toc):
            # Убеждаемся, что нет перекрытий
            if i > 0 and start_page <= merged_toc[i-1][3]:
                start_page = merged_toc[i-1][3] + 1
            
            # Проверяем валидность диапазона
            if start_page < len(all_text) and end_page >= start_page:
                # Собираем текст главы
                chapter_text = '\n'.join(all_text[start_page:end_page + 1])
                
                chapters.append({
                    "title": self._clean_title(title),
                    "text": chapter_text,
                    "start_page": start_page,
                    "end_page": end_page
                })
        
        print(f"📚 Создано {len(chapters)} глав из {len(toc)} элементов оглавления")
        
        # Проверяем покрытие
        covered_pages = set()
        for ch in chapters:
            for p in range(ch["start_page"], ch["end_page"] + 1):
                covered_pages.add(p)
        
        missing_pages = set(range(len(all_text))) - covered_pages
        if missing_pages:
            print(f"⚠️ Непокрытые страницы: {len(missing_pages)} из {len(all_text)}")
            
            # Добавляем непокрытые страницы к ближайшим главам
            for page in sorted(missing_pages):
                # Находим ближайшую главу
                for ch in chapters:
                    if ch["end_page"] == page - 1:
                        ch["end_page"] = page
                        ch["text"] += "\n" + all_text[page]
                        break
                    elif ch["start_page"] == page + 1:
                        ch["start_page"] = page
                        ch["text"] = all_text[page] + "\n" + ch["text"]
                        break
        
        return chapters
    
    def _split_by_pages(self, all_text, pages_per_chapter):
        """Разбивка на главы по количеству страниц (запасной вариант)"""
        chapters = []
        
        for i in range(0, len(all_text), pages_per_chapter):
            start_page = i
            end_page = min(i + pages_per_chapter - 1, len(all_text) - 1)
            
            # Собираем текст главы
            chapter_text = '\n'.join(all_text[start_page:end_page + 1])
            
            # Пытаемся найти заголовок
            title = self._find_chapter_title(chapter_text, len(chapters))
            
            chapters.append({
                "title": title,
                "text": chapter_text,
                "start_page": start_page,
                "end_page": end_page
            })
        
        return chapters
    
    def _clean_title(self, title):
        """Очищает заголовок от лишних символов"""
        # Убираем номера страниц в конце
        title = re.sub(r'\s*\d+\s*$', '', title)
        # Убираем лишние пробелы
        title = ' '.join(title.split())
        # Ограничиваем длину
        if len(title) > 150:
            title = title[:147] + "..."
        return title
    
    def _find_chapter_title(self, text, chapter_num):
        """Попытка найти заголовок главы"""
        lines = text.split('\n')[:20]
        
        # Паттерны для поиска заголовков
        patterns = [
            r"^(Chapter|CHAPTER|Глава)\s+(\d+|[IVX]+)",
            r"^(Part|PART|Часть)\s+(\d+|[IVX]+)",
            r"^(\d+\.)\s+[A-ZА-Я][a-zа-я]+",
            r"^(Section|SECTION|Раздел)\s+(\d+)",
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            for pattern in patterns:
                if re.match(pattern, line):
                    return self._clean_title(line)
            
            # Если строка выглядит как заголовок
            if (len(line) > 5 and len(line) < 100 and 
                not line.endswith('.') and 
                not line.endswith(',') and
                line[0].isupper()):
                words = line.split()
                if len(words) < 15:
                    return self._clean_title(line)
        
        return f"Часть {chapter_num + 1}"
    
    def _save_chapter(self, title, text, chapter_num, start_page, end_page):
        """Сохранение главы в JSON"""
        filename = f"chapter_{chapter_num:03d}.json"
        filepath = self.output_dir / filename
        
        # Очищаем текст
        text = self._clean_text(text)
        
        # Разбиваем на абзацы
        paragraphs = self._split_into_paragraphs(text)
        
        chapter_data = {
            "number": chapter_num,
            "title": title,
            "start_page": start_page,
            "end_page": end_page,
            "paragraphs": paragraphs,
            "word_count": len(text.split())
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=2)
    
    def _clean_text(self, text):
        """Очистка текста от артефактов с сохранением переносов строк"""
        # Удаляем только множественные пробелы и табы (НЕ переносы строк!)
        text = re.sub(r'[ \t]+', ' ', text)
        # Удаляем пробелы в начале и конце строк
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        # Убираем множественные пустые строки (но оставляем одиночные переносы!)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        return text.strip()
    
    def _split_into_paragraphs(self, text):
        """Разбивка текста на абзацы с сохранением внутренних переносов"""
        # Разделяем по двойным переводам строки
        paragraphs = text.split('\n\n')
        # Обрабатываем каждый параграф, сохраняя внутренние переносы
        cleaned_paragraphs = []
        for p in paragraphs:
            if p.strip():
                # Сохраняем одиночные переносы строк внутри параграфа
                # Убираем только пустые строки в начале и конце
                cleaned_p = p.strip()
                if len(cleaned_p) > 10:  # Фильтруем слишком короткие фрагменты
                    cleaned_paragraphs.append(cleaned_p)
        return cleaned_paragraphs
    
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
        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def _verify_extraction(self):
        """Проверка целостности извлечения"""
        print("\n🔍 Проверка целостности...")
        
        # Проверка покрытия страниц
        covered_pages = set()
        overlapping_pages = []
        
        for i, ch in enumerate(self.metadata["chapters"]):
            chapter_pages = set(range(ch["start_page"], ch["end_page"] + 1))
            
            # Проверка перекрытий
            overlap = covered_pages & chapter_pages
            if overlap:
                overlapping_pages.append((i, sorted(overlap)))
            
            covered_pages.update(chapter_pages)
        
        missing_pages = set(range(self.metadata["total_pages"])) - covered_pages
        
        if overlapping_pages:
            print(f"⚠️ Найдены перекрывающиеся страницы:")
            for ch_num, pages in overlapping_pages[:5]:
                print(f"   Глава {ch_num}: страницы {pages[:10]}...")
        
        if missing_pages:
            print(f"⚠️ Непокрытые страницы: {sorted(missing_pages)[:20]}...")
        
        if not overlapping_pages and not missing_pages:
            print("✅ Все страницы покрыты без перекрытий")
        
        # Статистика
        chapter_sizes = [ch["page_count"] for ch in self.metadata["chapters"]]
        print(f"\n📊 Статистика глав:")
        print(f"   Средний размер: {sum(chapter_sizes)/len(chapter_sizes):.1f} страниц")
        print(f"   Минимальный: {min(chapter_sizes)} страниц")
        print(f"   Максимальный: {max(chapter_sizes)} страниц")


if __name__ == "__main__":
    print("🚀 Запуск исправленного экстрактора PDF...")
    print("")
    
    extractor = FixedPDFExtractor("book.pdf")
    metadata = extractor.extract_all()
    
    print(f"\n✨ Готово!")
    print(f"   Результаты сохранены в папке extracted_fixed/")
    print(f"   Теперь можно запустить перевод с правильной структурой глав")