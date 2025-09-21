#!/usr/bin/env python3
"""
Универсальный экстрактор для PDF и текстовых файлов
Объединяет лучшие функции из всех версий экстракторов
"""

import fitz
import os
import json
import re
from pathlib import Path
from tqdm import tqdm
import hashlib
from typing import List, Dict, Tuple, Optional
import unicodedata


class UniversalBookExtractor:
    """Универсальный экстрактор для любых форматов книг"""
    
    def __init__(self, input_path, output_dir="extracted_fixed"):
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Определяем формат файла
        self.file_format = self._detect_format()
        
        # Общие метаданные
        self.metadata = {
            "total_pages": 0,
            "chapters": [],
            "extraction_complete": False,
            "book_title": "",
            "book_info": {},
            "source_format": self.file_format,
            "extraction_method": "",
            "statistics": {}
        }
        
        # Настройки экстракции
        self.settings = {
            "min_paragraph_length": 10,
            "sentences_per_paragraph": 8,  # Для текста без форматирования
            "chars_per_chapter": 10000,     # Для разбивки по размеру
            "pages_per_chapter": 30,         # Для PDF без оглавления
            "smart_paragraph_split": True,   # Умное разбиение на параграфы
            "preserve_formatting": True,     # Сохранять форматирование где возможно
            "extract_images": True,          # Извлекать изображения
            "clean_ocr_artifacts": True      # Очищать OCR артефакты
        }
    
    def _detect_format(self) -> str:
        """Определение формата файла"""
        suffix = self.input_path.suffix.lower()
        if suffix == '.pdf':
            return 'pdf'
        elif suffix in ['.txt', '.text']:
            return 'txt'
        elif suffix == '.md':
            return 'markdown'
        else:
            # Пытаемся определить по содержимому
            try:
                with open(self.input_path, 'r', encoding='utf-8') as f:
                    f.read(1000)
                return 'txt'
            except:
                return 'pdf'
    
    def extract_all(self):
        """Главный метод извлечения"""
        print(f"📚 Обработка файла: {self.input_path.name}")
        print(f"📂 Формат: {self.file_format.upper()}")
        
        if self.file_format == 'pdf':
            return self._extract_from_pdf()
        else:
            return self._extract_from_text()
    
    def _extract_from_pdf(self):
        """Извлечение из PDF с продвинутыми возможностями"""
        print("📖 Открываем PDF документ...")
        
        try:
            doc = fitz.open(str(self.input_path))
        except Exception as e:
            print(f"❌ Ошибка открытия PDF: {e}")
            return None
        
        self.metadata["total_pages"] = len(doc)
        self.metadata["extraction_method"] = "pdf_advanced"
        
        # Извлекаем метаданные
        self._extract_pdf_metadata(doc)
        
        # Извлекаем весь текст постранично
        all_pages = []
        print(f"📄 Извлекаем текст из {len(doc)} страниц...")
        
        for page_num in tqdm(range(len(doc)), desc="Чтение страниц"):
            page = doc[page_num]
            
            # Извлекаем текст с разными методами для лучшего качества
            text = self._extract_page_text(page)
            
            # Проверяем на изображения
            images = []
            if self.settings["extract_images"]:
                images = self._extract_page_images(page, page_num)
            
            all_pages.append({
                'page_num': page_num,
                'text': text,
                'images': images
            })
        
        # Определяем структуру глав
        chapters_data = self._determine_chapter_structure(doc, all_pages)
        
        # Сохраняем главы
        self._save_chapters(chapters_data)
        
        doc.close()
        
        self._finalize_extraction()
        return self.metadata
    
    def _extract_from_text(self):
        """Извлечение из текстового файла с умным разбиением"""
        print("📖 Открываем текстовый файл...")
        
        try:
            with open(self.input_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
        except UnicodeDecodeError:
            # Пробуем другие кодировки
            for encoding in ['latin-1', 'cp1251', 'cp1252']:
                try:
                    with open(self.input_path, 'r', encoding=encoding) as f:
                        full_text = f.read()
                    print(f"⚠️ Использована кодировка: {encoding}")
                    break
                except:
                    continue
            else:
                print("❌ Не удалось прочитать файл")
                return None
        
        self.metadata["extraction_method"] = "text_smart"
        
        # Анализируем структуру текста
        text_stats = self._analyze_text_structure(full_text)
        self.metadata["statistics"] = text_stats
        
        print(f"📊 Статистика текста:")
        print(f"   • Символов: {text_stats['char_count']:,}")
        print(f"   • Слов: {text_stats['word_count']:,}")
        print(f"   • Предложений: {text_stats['sentence_count']:,}")
        print(f"   • Параграфов: {text_stats['paragraph_count']:,}")
        print(f"   • Переносов строк: {text_stats['newline_count']:,}")
        
        # Определяем главы
        chapters_data = self._detect_text_chapters(full_text, text_stats)
        
        # Сохраняем главы
        self._save_chapters(chapters_data)
        
        self._finalize_extraction()
        return self.metadata
    
    def _extract_pdf_metadata(self, doc):
        """Извлечение метаданных PDF"""
        metadata = doc.metadata
        if metadata:
            self.metadata["book_info"] = {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "keywords": metadata.get("keywords", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": str(metadata.get("creationDate", "")),
                "modification_date": str(metadata.get("modDate", ""))
            }
            
            # Пытаемся извлечь название
            if metadata.get("title"):
                self.metadata["book_title"] = metadata.get("title")
            else:
                # Используем имя файла
                self.metadata["book_title"] = self.input_path.stem
    
    def _extract_page_text(self, page) -> str:
        """Продвинутое извлечение текста со страницы"""
        # Метод 1: Стандартное извлечение
        text = page.get_text()
        
        # Если текста мало, пробуем другие методы
        if len(text.strip()) < 100:
            # Метод 2: Извлечение блоками
            blocks = page.get_text("blocks")
            text = "\n".join([b[4] for b in blocks if b[4].strip()])
        
        # Очищаем артефакты OCR если нужно
        if self.settings["clean_ocr_artifacts"]:
            text = self._clean_ocr_artifacts(text)
        
        return text
    
    def _extract_page_images(self, page, page_num) -> List[Dict]:
        """Извлечение изображений со страницы"""
        images = []
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            # Получаем данные изображения
            xref = img[0]
            pix = fitz.Pixmap(page.parent, xref)
            
            if pix.n - pix.alpha < 4:  # GRAY или RGB
                img_data = {
                    "page": page_num,
                    "index": img_index,
                    "width": pix.width,
                    "height": pix.height,
                    "placeholder": f"[IMAGE_P{page_num:03d}_I{img_index:02d}]"
                }
                images.append(img_data)
            
            pix = None
        
        return images
    
    def _determine_chapter_structure(self, doc, all_pages) -> List[Dict]:
        """Определение структуры глав для PDF"""
        chapters = []
        
        # Пробуем разные методы
        toc = doc.get_toc()
        
        if toc and len(toc) > 0:
            print(f"📑 Используем оглавление ({len(toc)} элементов)")
            chapters = self._extract_chapters_by_toc(doc, all_pages, toc)
        else:
            # Ищем главы по паттернам
            print("🔍 Ищем главы по паттернам...")
            chapters = self._detect_chapters_by_patterns(all_pages)
            
            if not chapters or len(chapters) < 2:
                # Разбиваем по страницам
                print(f"📊 Разбиваем по {self.settings['pages_per_chapter']} страниц")
                chapters = self._split_by_pages(all_pages)
        
        return chapters
    
    def _extract_chapters_by_toc(self, doc, all_pages, toc) -> List[Dict]:
        """Извлечение глав по оглавлению"""
        chapters = []
        
        # Фильтруем TOC - оставляем только главы верхнего уровня
        main_chapters = []
        for item in toc:
            level, title, page_num = item[0], item[1], item[2] - 1
            if level <= 2 and page_num >= 0:  # Уровень 1 или 2
                main_chapters.append({
                    'title': self._clean_chapter_title(title),
                    'start_page': page_num,
                    'level': level
                })
        
        if not main_chapters:
            return []
        
        # Определяем границы глав
        for i, chapter in enumerate(main_chapters):
            if i + 1 < len(main_chapters):
                end_page = main_chapters[i + 1]['start_page']
            else:
                end_page = len(all_pages)
            
            # Собираем текст главы
            chapter_pages = all_pages[chapter['start_page']:end_page]
            chapter_text = "\n".join([p['text'] for p in chapter_pages])
            
            # Собираем изображения
            chapter_images = []
            for p in chapter_pages:
                chapter_images.extend(p.get('images', []))
            
            chapters.append({
                'title': chapter['title'],
                'text': chapter_text,
                'start_page': chapter['start_page'],
                'end_page': end_page,
                'pages': chapter_pages,
                'images': chapter_images
            })
        
        return chapters
    
    def _detect_chapters_by_patterns(self, all_pages) -> List[Dict]:
        """Определение глав по паттернам в тексте"""
        chapters = []
        chapter_patterns = [
            r'^(Chapter|CHAPTER|Глава)\s+(\d+|[IVX]+)',
            r'^(Part|PART|Часть)\s+(\d+|[IVX]+)',
            r'^(\d+)\.\s+[A-ZА-Я][a-zа-яA-Za-z\s]+',
            r'^(Section|SECTION|Раздел)\s+(\d+|[IVX]+)',
        ]
        
        current_chapter = None
        
        for page_idx, page_data in enumerate(all_pages):
            lines = page_data['text'].split('\n')[:10]  # Проверяем первые 10 строк
            
            for line in lines:
                line = line.strip()
                if len(line) < 3:
                    continue
                    
                for pattern in chapter_patterns:
                    if re.match(pattern, line):
                        # Сохраняем предыдущую главу
                        if current_chapter:
                            chapters.append(current_chapter)
                        
                        # Начинаем новую главу
                        current_chapter = {
                            'title': self._clean_chapter_title(line),
                            'text': page_data['text'],
                            'start_page': page_idx,
                            'end_page': page_idx + 1,
                            'pages': [page_data],
                            'images': page_data.get('images', [])
                        }
                        break
                else:
                    continue
                break
            else:
                # Продолжаем текущую главу
                if current_chapter:
                    current_chapter['text'] += "\n" + page_data['text']
                    current_chapter['end_page'] = page_idx + 1
                    current_chapter['pages'].append(page_data)
                    current_chapter['images'].extend(page_data.get('images', []))
        
        # Добавляем последнюю главу
        if current_chapter:
            chapters.append(current_chapter)
        
        return chapters
    
    def _split_by_pages(self, all_pages) -> List[Dict]:
        """Разбивка на главы по количеству страниц"""
        chapters = []
        pages_per_chapter = self.settings['pages_per_chapter']
        
        for i in range(0, len(all_pages), pages_per_chapter):
            chapter_pages = all_pages[i:i + pages_per_chapter]
            chapter_text = "\n".join([p['text'] for p in chapter_pages])
            
            # Собираем изображения
            chapter_images = []
            for p in chapter_pages:
                chapter_images.extend(p.get('images', []))
            
            chapter_num = len(chapters) + 1
            chapters.append({
                'title': f"Часть {chapter_num}",
                'text': chapter_text,
                'start_page': i,
                'end_page': min(i + pages_per_chapter, len(all_pages)),
                'pages': chapter_pages,
                'images': chapter_images
            })
        
        return chapters
    
    def _analyze_text_structure(self, text: str) -> Dict:
        """Анализ структуры текста"""
        stats = {
            'char_count': len(text),
            'word_count': len(text.split()),
            'newline_count': text.count('\n'),
            'double_newline_count': text.count('\n\n'),
            'sentence_count': 0,
            'paragraph_count': 0,
            'has_chapters': False,
            'avg_paragraph_length': 0
        }
        
        # Считаем предложения
        sentences = self._split_into_sentences(text)
        stats['sentence_count'] = len(sentences)
        
        # Считаем параграфы
        if stats['double_newline_count'] > 10:
            # Есть явное разделение на параграфы
            paragraphs = text.split('\n\n')
            stats['paragraph_count'] = len([p for p in paragraphs if len(p.strip()) > 20])
        elif stats['newline_count'] > stats['sentence_count'] * 0.5:
            # Каждое предложение с новой строки
            paragraphs = text.split('\n')
            stats['paragraph_count'] = len([p for p in paragraphs if len(p.strip()) > 20])
        else:
            # Нет явных параграфов
            stats['paragraph_count'] = 0
        
        if stats['paragraph_count'] > 0:
            stats['avg_paragraph_length'] = stats['char_count'] / stats['paragraph_count']
        
        # Проверяем наличие глав
        chapter_markers = ['Chapter', 'CHAPTER', 'Part', 'PART', 'Глава', 'Часть']
        for marker in chapter_markers:
            if marker in text:
                stats['has_chapters'] = True
                break
        
        return stats
    
    def _detect_text_chapters(self, full_text: str, text_stats: Dict) -> List[Dict]:
        """Определение глав в текстовом файле"""
        chapters = []
        
        # Метод 1: Поиск явных маркеров глав
        if text_stats['has_chapters']:
            chapters = self._find_chapter_markers(full_text)
        
        # Метод 2: Разбивка по размеру с умными параграфами
        if not chapters:
            print("📊 Главы не найдены, создаем структуру...")
            
            # Если нет параграфов, создаем их из предложений
            if text_stats['paragraph_count'] == 0:
                print(f"🔄 Создаем параграфы из {text_stats['sentence_count']} предложений...")
                paragraphs = self._create_smart_paragraphs(full_text)
            else:
                # Используем существующие параграфы
                if text_stats['double_newline_count'] > 10:
                    paragraphs = full_text.split('\n\n')
                else:
                    paragraphs = full_text.split('\n')
                
                paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 20]
            
            # Группируем параграфы в главы
            chapters = self._group_paragraphs_into_chapters(paragraphs)
        
        return chapters
    
    def _find_chapter_markers(self, text: str) -> List[Dict]:
        """Поиск глав по маркерам"""
        chapters = []
        
        # Паттерны для поиска глав
        patterns = [
            r'(Chapter|CHAPTER)\s+(\d+|[IVX]+)[^\n]*',
            r'(Part|PART)\s+(\d+|[IVX]+)[^\n]*',
            r'(Глава|ГЛАВА)\s+(\d+|[IVX]+)[^\n]*',
            r'(Часть|ЧАСТЬ)\s+(\d+|[IVX]+)[^\n]*',
            r'^\d+\.\s+[A-ZА-Я][^\n]+',
        ]
        
        # Компилируем паттерны
        combined_pattern = '|'.join(patterns)
        
        # Ищем все совпадения
        matches = list(re.finditer(combined_pattern, text, re.MULTILINE))
        
        if not matches:
            return []
        
        print(f"📚 Найдено {len(matches)} глав")
        
        for i, match in enumerate(matches):
            start_pos = match.start()
            title = self._clean_chapter_title(match.group(0))
            
            # Определяем конец главы
            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text)
            
            chapter_text = text[start_pos:end_pos]
            
            chapters.append({
                'title': title,
                'text': chapter_text,
                'start_pos': start_pos,
                'end_pos': end_pos
            })
        
        return chapters
    
    def _create_smart_paragraphs(self, text: str) -> List[str]:
        """Создание умных параграфов из неформатированного текста"""
        # Разбиваем на предложения
        sentences = self._split_into_sentences(text)
        
        paragraphs = []
        current_para = []
        sentence_count = 0
        
        for i, sentence in enumerate(sentences):
            current_para.append(sentence)
            sentence_count += 1
            
            # Условия для создания нового параграфа
            should_break = False
            
            # 1. Достигли лимита предложений
            if sentence_count >= self.settings['sentences_per_paragraph']:
                should_break = True
            
            # 2. Конец логического блока
            elif self._is_logical_break(sentence):
                should_break = True
            
            # 3. Начало нового блока
            elif i + 1 < len(sentences) and self._is_new_section(sentences[i + 1]):
                should_break = True
            
            if should_break:
                if current_para:
                    para_text = ' '.join(current_para).strip()
                    if para_text:
                        paragraphs.append(para_text)
                current_para = []
                sentence_count = 0
        
        # Добавляем последний параграф
        if current_para:
            para_text = ' '.join(current_para).strip()
            if para_text:
                paragraphs.append(para_text)
        
        print(f"✅ Создано {len(paragraphs)} параграфов")
        return paragraphs
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Умное разбиение текста на предложения"""
        # Защищаем аббревиатуры
        protected = text
        
        # Список распространенных аббревиатур
        abbrevs = [
            'Mr', 'Mrs', 'Dr', 'Ms', 'Prof', 'Sr', 'Jr',
            'Inc', 'Ltd', 'Corp', 'Co', 'vs', 'etc', 'i.e', 'e.g',
            'Ph.D', 'M.D', 'B.A', 'M.A', 'B.S', 'M.S'
        ]
        
        for abbr in abbrevs:
            protected = re.sub(f'\\b{re.escape(abbr)}\\.', f'{abbr}<DOT>', protected, flags=re.IGNORECASE)
        
        # Защищаем числа с точками
        protected = re.sub(r'(\d+)\.(\d+)', r'\1<DOT>\2', protected)
        
        # Защищаем инициалы
        protected = re.sub(r'\b([A-Z])\.', r'\1<DOT>', protected)
        
        # Разбиваем по знакам препинания
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)
        
        # Восстанавливаем точки
        sentences = [s.replace('<DOT>', '.') for s in sentences]
        
        # Фильтруем короткие и пустые
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        return sentences
    
    def _is_logical_break(self, sentence: str) -> bool:
        """Проверка на логический конец раздела"""
        end_markers = [
            'In conclusion', 'To summarize', 'In summary', 'Finally',
            'Therefore', 'Thus', 'Hence', 'As a result',
            'В заключение', 'Таким образом', 'Итак', 'Следовательно'
        ]
        
        sentence_lower = sentence.lower()
        for marker in end_markers:
            if marker.lower() in sentence_lower[:50]:  # Проверяем начало предложения
                return True
        
        # Проверяем на конец главы/раздела
        if re.search(r'(Chapter|Part|Section)\s+\d+', sentence):
            return True
        
        return False
    
    def _is_new_section(self, sentence: str) -> bool:
        """Проверка на начало нового раздела"""
        start_markers = [
            'Chapter', 'Part', 'Section', 'Introduction',
            'Глава', 'Часть', 'Раздел', 'Введение',
            'First', 'Second', 'Third', 'Next', 'Another',
            'Первый', 'Второй', 'Третий', 'Далее'
        ]
        
        # Проверяем начало предложения
        first_words = sentence.split()[:3]
        for word in first_words:
            if word.strip('.,!?:;') in start_markers:
                return True
        
        # Проверяем на нумерованный список
        if re.match(r'^\d+[\.)]\s+', sentence):
            return True
        
        return False
    
    def _group_paragraphs_into_chapters(self, paragraphs: List[str]) -> List[Dict]:
        """Группировка параграфов в главы"""
        chapters = []
        chars_per_chapter = self.settings['chars_per_chapter']
        
        current_chapter = []
        current_size = 0
        chapter_num = 1
        
        for para in paragraphs:
            para_size = len(para)
            
            # Проверяем, не пора ли создать новую главу
            if current_size + para_size > chars_per_chapter and current_chapter:
                # Сохраняем текущую главу
                chapter_text = '\n\n'.join(current_chapter)
                chapters.append({
                    'title': f"Часть {chapter_num}",
                    'text': chapter_text,
                    'paragraphs': current_chapter.copy()
                })
                
                current_chapter = [para]
                current_size = para_size
                chapter_num += 1
            else:
                current_chapter.append(para)
                current_size += para_size
        
        # Сохраняем последнюю главу
        if current_chapter:
            chapter_text = '\n\n'.join(current_chapter)
            chapters.append({
                'title': f"Часть {chapter_num}",
                'text': chapter_text,
                'paragraphs': current_chapter
            })
        
        return chapters
    
    def _clean_chapter_title(self, title: str) -> str:
        """Очистка заголовка главы"""
        # Убираем лишние символы
        title = re.sub(r'[=\-_*#]{3,}', '', title)
        title = re.sub(r'^\s*[\d.]+\s*', '', title)  # Убираем номера в начале
        title = ' '.join(title.split())  # Нормализуем пробелы
        
        # Ограничиваем длину
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Если заголовок пустой, даем стандартный
        if not title.strip():
            title = "Без названия"
        
        return title
    
    def _clean_ocr_artifacts(self, text: str) -> str:
        """Очистка артефактов OCR"""
        # Убираем лигатуры
        ligatures = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}
        for lig, replacement in ligatures.items():
            text = text.replace(lig, replacement)
        
        # Нормализуем Unicode
        text = unicodedata.normalize('NFKC', text)
        
        # Убираем множественные пробелы
        text = re.sub(r' +', ' ', text)
        
        # Убираем пробелы перед знаками препинания
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        
        # Исправляем разорванные слова
        text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)
        
        return text
    
    def _save_chapters(self, chapters_data: List[Dict]):
        """Сохранение глав в файлы"""
        print(f"💾 Сохраняем {len(chapters_data)} глав...")
        
        for chapter_num, chapter_data in enumerate(tqdm(chapters_data, desc="Сохранение глав")):
            # Подготавливаем параграфы
            if 'paragraphs' in chapter_data:
                # Уже есть готовые параграфы
                paragraphs = chapter_data['paragraphs']
            else:
                # Создаем параграфы из текста
                text = chapter_data.get('text', '')
                if self.settings['smart_paragraph_split']:
                    paragraphs = self._smart_split_into_paragraphs(text)
                else:
                    paragraphs = text.split('\n\n')
                    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > self.settings['min_paragraph_length']]
            
            # Вставляем плейсхолдеры изображений
            if 'images' in chapter_data and chapter_data['images']:
                paragraphs = self._insert_image_placeholders(paragraphs, chapter_data['images'])
            
            # Сохраняем главу
            self._save_single_chapter(
                chapter_data['title'],
                paragraphs,
                chapter_num,
                chapter_data
            )
            
            # Обновляем метаданные
            self.metadata["chapters"].append({
                "number": chapter_num,
                "title": chapter_data['title'],
                "start_page": chapter_data.get('start_page', 0),
                "end_page": chapter_data.get('end_page', 0),
                "paragraph_count": len(paragraphs),
                "word_count": sum(len(p.split()) for p in paragraphs),
                "char_count": sum(len(p) for p in paragraphs),
                "has_images": len(chapter_data.get('images', [])) > 0,
                "status": "extracted"
            })
    
    def _smart_split_into_paragraphs(self, text: str) -> List[str]:
        """Умное разбиение текста на параграфы с учетом структуры"""
        # Если есть явные параграфы - используем их
        if '\n\n' in text and text.count('\n\n') > 5:
            paragraphs = text.split('\n\n')
            return [p.strip() for p in paragraphs if len(p.strip()) > self.settings['min_paragraph_length']]
        
        # Если каждое предложение с новой строки
        if '\n' in text and text.count('\n') > text.count('. ') * 0.8:
            paragraphs = []
            current_para = []
            
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    if current_para:
                        paragraphs.append(' '.join(current_para))
                        current_para = []
                else:
                    current_para.append(line)
            
            if current_para:
                paragraphs.append(' '.join(current_para))
            
            return paragraphs
        
        # Иначе создаем параграфы из предложений
        return self._create_smart_paragraphs(text)
    
    def _insert_image_placeholders(self, paragraphs: List[str], images: List[Dict]) -> List[str]:
        """Вставка плейсхолдеров изображений в нужные места"""
        # Простая логика: вставляем изображения равномерно
        if not images:
            return paragraphs
        
        result = []
        images_per_para = max(1, len(paragraphs) // len(images))
        image_idx = 0
        
        for i, para in enumerate(paragraphs):
            result.append(para)
            
            # Вставляем изображение после каждого N-го параграфа
            if (i + 1) % images_per_para == 0 and image_idx < len(images):
                result.append(images[image_idx]['placeholder'])
                image_idx += 1
        
        # Добавляем оставшиеся изображения в конец
        while image_idx < len(images):
            result.append(images[image_idx]['placeholder'])
            image_idx += 1
        
        return result
    
    def _save_single_chapter(self, title: str, paragraphs: List[str], chapter_num: int, extra_data: Dict):
        """Сохранение одной главы в JSON"""
        filename = f"chapter_{chapter_num:03d}.json"
        filepath = self.output_dir / filename
        
        chapter_data = {
            "number": chapter_num,
            "title": title,
            "paragraphs": paragraphs,
            "paragraph_count": len(paragraphs),
            "word_count": sum(len(p.split()) for p in paragraphs),
            "char_count": sum(len(p) for p in paragraphs),
            "source_format": self.file_format,
            "extraction_method": self.metadata["extraction_method"]
        }
        
        # Добавляем дополнительные данные если есть
        if 'start_page' in extra_data:
            chapter_data['start_page'] = extra_data['start_page']
        if 'end_page' in extra_data:
            chapter_data['end_page'] = extra_data['end_page']
        if 'images' in extra_data and extra_data['images']:
            chapter_data['image_count'] = len(extra_data['images'])
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chapter_data, f, ensure_ascii=False, indent=2)
    
    def _finalize_extraction(self):
        """Финализация процесса извлечения"""
        self.metadata["extraction_complete"] = True
        
        # Подсчет общей статистики
        total_words = sum(ch['word_count'] for ch in self.metadata['chapters'])
        total_chars = sum(ch['char_count'] for ch in self.metadata['chapters'])
        total_paragraphs = sum(ch['paragraph_count'] for ch in self.metadata['chapters'])
        
        self.metadata['statistics'] = {
            'total_chapters': len(self.metadata['chapters']),
            'total_words': total_words,
            'total_chars': total_chars,
            'total_paragraphs': total_paragraphs,
            'avg_chapter_words': total_words // max(1, len(self.metadata['chapters'])),
            'avg_paragraph_words': total_words // max(1, total_paragraphs)
        }
        
        # Сохраняем метаданные
        self._save_metadata()
        
        # Выводим итоги
        print(f"\n✅ Извлечение завершено успешно!")
        print(f"📊 Статистика:")
        print(f"   • Глав: {self.metadata['statistics']['total_chapters']}")
        print(f"   • Параграфов: {self.metadata['statistics']['total_paragraphs']}")
        print(f"   • Слов: {self.metadata['statistics']['total_words']:,}")
        print(f"   • Символов: {self.metadata['statistics']['total_chars']:,}")
        
        # Проверка покрытия для PDF
        if self.file_format == 'pdf' and self.metadata.get('total_pages', 0) > 0:
            self._verify_page_coverage()
    
    def _save_metadata(self):
        """Сохранение метаданных"""
        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def _verify_page_coverage(self):
        """Проверка покрытия страниц для PDF"""
        if self.file_format != 'pdf':
            return
        
        covered_pages = set()
        for chapter in self.metadata['chapters']:
            for page in range(chapter.get('start_page', 0), chapter.get('end_page', 0)):
                covered_pages.add(page)
        
        total_pages = self.metadata.get('total_pages', 0)
        all_pages = set(range(total_pages))
        missing_pages = all_pages - covered_pages
        
        if missing_pages:
            print(f"⚠️  Не покрыты страницы: {sorted(missing_pages)[:20]}...")
            if len(missing_pages) > 20:
                print(f"    (и еще {len(missing_pages) - 20} страниц)")
        else:
            print("✅ Все страницы PDF покрыты")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Универсальный экстрактор книг')
    parser.add_argument('input', nargs='?', help='Путь к файлу книги')
    parser.add_argument('--output-dir', '-o', default='extracted_fixed', 
                      help='Директория для сохранения (по умолчанию: extracted_fixed)')
    parser.add_argument('--sentences-per-para', '-s', type=int, default=8,
                      help='Предложений в параграфе для неформатированного текста (по умолчанию: 8)')
    parser.add_argument('--chars-per-chapter', '-c', type=int, default=10000,
                      help='Символов в главе при разбивке по размеру (по умолчанию: 10000)')
    parser.add_argument('--pages-per-chapter', '-p', type=int, default=30,
                      help='Страниц в главе для PDF без оглавления (по умолчанию: 30)')
    parser.add_argument('--no-images', action='store_true',
                      help='Не извлекать изображения из PDF')
    parser.add_argument('--no-ocr-clean', action='store_true',
                      help='Не очищать OCR артефакты')
    
    args = parser.parse_args()
    
    # Определяем входной файл
    if args.input:
        input_file = args.input
    else:
        # Ищем book.pdf или book.txt
        if os.path.exists("book.pdf"):
            input_file = "book.pdf"
        elif os.path.exists("book.txt"):
            input_file = "book.txt"
        else:
            print("❌ Файл не найден!")
            print("   Укажите путь к файлу или поместите book.pdf/book.txt в текущую директорию")
            return
    
    if not os.path.exists(input_file):
        print(f"❌ Файл {input_file} не существует!")
        return
    
    print("="*60)
    print("📚 УНИВЕРСАЛЬНЫЙ ЭКСТРАКТОР КНИГ v2.0")
    print("="*60)
    
    # Создаем экстрактор
    extractor = UniversalBookExtractor(input_file, args.output_dir)
    
    # Настраиваем параметры
    if args.sentences_per_para:
        extractor.settings['sentences_per_paragraph'] = args.sentences_per_para
    if args.chars_per_chapter:
        extractor.settings['chars_per_chapter'] = args.chars_per_chapter
    if args.pages_per_chapter:
        extractor.settings['pages_per_chapter'] = args.pages_per_chapter
    if args.no_images:
        extractor.settings['extract_images'] = False
    if args.no_ocr_clean:
        extractor.settings['clean_ocr_artifacts'] = False
    
    # Запускаем извлечение
    metadata = extractor.extract_all()
    
    if metadata:
        print("\n" + "="*60)
        print("📋 РЕЗУЛЬТАТЫ ИЗВЛЕЧЕНИЯ:")
        print("="*60)
        
        for chapter in metadata['chapters'][:10]:  # Показываем первые 10 глав
            print(f"  Глава {chapter['number']:03d}: {chapter['title'][:50]:50s} "
                  f"({chapter['paragraph_count']:3d} пар., {chapter['word_count']:5d} слов)")
        
        if len(metadata['chapters']) > 10:
            print(f"  ... и еще {len(metadata['chapters']) - 10} глав")
        
        print("\n✅ Готово для дальнейшей обработки!")
        print("   • Перевод: python3 03_translate_parallel.py --all")
        print("   • Фигуры:  python3 02_extract_figures.py")
        print("   • Контекст: python3 09_extract_book_context.py")


if __name__ == "__main__":
    main()