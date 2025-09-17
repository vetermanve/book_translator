#!/usr/bin/env python3
"""
Пост-процессинг переведенного текста - удаление нежелательного контента
на основе черного списка слов, фраз и паттернов
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
import shutil
from tqdm import tqdm

class TranslationPostProcessor:
    def __init__(self, config_file="blacklist_config.json", 
                 input_dir="translations", 
                 output_dir="translations_filtered"):
        """
        Инициализация пост-процессора
        
        Args:
            config_file: Путь к файлу конфигурации с черным списком
            input_dir: Директория с исходными переводами
            output_dir: Директория для отфильтрованных переводов
        """
        self.config_file = Path(config_file)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # Загружаем конфигурацию
        self.config = self.load_config()
        
        # Компилируем регулярные выражения для паттернов
        self.compiled_patterns = self.compile_patterns()
        
        # Статистика удалений
        self.stats = {
            "total_chapters": 0,
            "total_paragraphs": 0,
            "removed_paragraphs": 0,
            "modified_paragraphs": 0,
            "removed_phrases": {},
            "removed_symbols": {},
            "removed_patterns": {}
        }
        
        # Создаем выходную директорию
        self.output_dir.mkdir(exist_ok=True)
        
        # Логирование удалений
        self.log_file = self.output_dir / "postprocess_log.txt"
        self.log_entries = []
        
    def load_config(self) -> Dict:
        """Загрузка конфигурации из JSON файла"""
        if not self.config_file.exists():
            print(f"⚠️ Файл конфигурации {self.config_file} не найден!")
            print("   Создаем конфигурацию по умолчанию...")
            default_config = {
                "blacklist": {
                    "phrases": [],
                    "symbols": [],
                    "patterns": []
                },
                "settings": {
                    "remove_empty_paragraphs": True,
                    "case_sensitive": False,
                    "trim_whitespace": True,
                    "min_paragraph_length": 10,
                    "log_removals": True
                }
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            return default_config
            
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def compile_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """Компилирует регулярные выражения из конфигурации"""
        compiled = []
        patterns = self.config.get("blacklist", {}).get("patterns", [])
        
        for pattern_info in patterns:
            if isinstance(pattern_info, dict):
                pattern_str = pattern_info.get("pattern", "")
                description = pattern_info.get("description", "")
            else:
                pattern_str = pattern_info
                description = pattern_str
            
            if pattern_str:
                flags = 0 if self.config["settings"]["case_sensitive"] else re.IGNORECASE
                try:
                    compiled_pattern = re.compile(pattern_str, flags)
                    compiled.append((compiled_pattern, description))
                except re.error as e:
                    print(f"⚠️ Ошибка компиляции паттерна '{pattern_str}': {e}")
        
        return compiled
    
    def remove_blacklisted_content(self, text: str, context: str = "") -> str:
        """
        Удаляет запрещенный контент из текста
        
        Args:
            text: Исходный текст
            context: Контекст для логирования (например, "Chapter 1, Paragraph 5")
            
        Returns:
            Отфильтрованный текст
        """
        if not text:
            return text
        
        original_text = text
        settings = self.config["settings"]
        
        # 1. Удаляем символы
        for symbol in self.config["blacklist"].get("symbols", []):
            if symbol in text:
                count = text.count(symbol)
                text = text.replace(symbol, "")
                if settings["log_removals"] and count > 0:
                    self.stats["removed_symbols"][symbol] = \
                        self.stats["removed_symbols"].get(symbol, 0) + count
                    self.log_entries.append(
                        f"{context}: Удален символ '{symbol}' ({count} раз)"
                    )
        
        # 2. Удаляем фразы
        for phrase in self.config["blacklist"].get("phrases", []):
            if not settings["case_sensitive"]:
                # Регистронезависимый поиск
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                matches = pattern.findall(text)
                if matches:
                    text = pattern.sub("", text)
                    count = len(matches)
                    self.stats["removed_phrases"][phrase] = \
                        self.stats["removed_phrases"].get(phrase, 0) + count
                    if settings["log_removals"]:
                        self.log_entries.append(
                            f"{context}: Удалена фраза '{phrase}' ({count} раз)"
                        )
            else:
                if phrase in text:
                    count = text.count(phrase)
                    text = text.replace(phrase, "")
                    self.stats["removed_phrases"][phrase] = \
                        self.stats["removed_phrases"].get(phrase, 0) + count
                    if settings["log_removals"]:
                        self.log_entries.append(
                            f"{context}: Удалена фраза '{phrase}' ({count} раз)"
                        )
        
        # 3. Удаляем по паттернам
        for pattern, description in self.compiled_patterns:
            matches = pattern.findall(text)
            if matches:
                text = pattern.sub("", text)
                count = len(matches)
                self.stats["removed_patterns"][description] = \
                    self.stats["removed_patterns"].get(description, 0) + count
                if settings["log_removals"]:
                    self.log_entries.append(
                        f"{context}: Удален паттерн '{description}' ({count} раз)"
                    )
        
        # 4. Очищаем лишние пробелы если нужно
        if settings["trim_whitespace"]:
            # Убираем множественные пробелы
            text = re.sub(r' +', ' ', text)
            # Убираем пробелы в начале и конце строк
            lines = text.split('\n')
            lines = [line.strip() for line in lines]
            text = '\n'.join(lines)
            # Убираем множественные переносы строк
            text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Проверяем, изменился ли текст
        if text != original_text:
            self.stats["modified_paragraphs"] += 1
        
        return text
    
    def is_paragraph_empty(self, text: str) -> bool:
        """
        Проверяет, является ли параграф пустым после фильтрации
        
        Args:
            text: Текст параграфа
            
        Returns:
            True если параграф пустой или слишком короткий
        """
        if not text:
            return True
        
        # Убираем все whitespace для проверки
        cleaned = re.sub(r'\s+', '', text)
        
        # Проверяем минимальную длину
        min_length = self.config["settings"].get("min_paragraph_length", 10)
        
        return len(cleaned) < min_length
    
    def process_chapter(self, chapter_data: Dict, chapter_name: str) -> Dict:
        """
        Обрабатывает одну главу
        
        Args:
            chapter_data: Данные главы
            chapter_name: Имя файла главы для логирования
            
        Returns:
            Отфильтрованные данные главы
        """
        self.stats["total_chapters"] += 1
        
        # Копируем структуру главы
        filtered_chapter = {
            "number": chapter_data.get("number", 0),
            "title": chapter_data.get("title", ""),
            "start_page": chapter_data.get("start_page", 0),
            "end_page": chapter_data.get("end_page", 0),
            "paragraphs": []
        }
        
        # Фильтруем заголовок
        if filtered_chapter["title"]:
            filtered_chapter["title"] = self.remove_blacklisted_content(
                filtered_chapter["title"],
                f"{chapter_name}: Title"
            )
        
        # Обрабатываем параграфы
        paragraphs = chapter_data.get("paragraphs", [])
        
        for idx, paragraph in enumerate(paragraphs):
            self.stats["total_paragraphs"] += 1
            
            # Пропускаем изображения
            if paragraph and paragraph.startswith('[IMAGE_'):
                filtered_chapter["paragraphs"].append(paragraph)
                continue
            
            # Фильтруем контент
            context = f"{chapter_name}, Paragraph {idx + 1}"
            filtered_text = self.remove_blacklisted_content(paragraph, context)
            
            # Проверяем, не стал ли параграф пустым
            if self.config["settings"]["remove_empty_paragraphs"]:
                if not self.is_paragraph_empty(filtered_text):
                    filtered_chapter["paragraphs"].append(filtered_text)
                else:
                    self.stats["removed_paragraphs"] += 1
                    if self.config["settings"]["log_removals"]:
                        self.log_entries.append(
                            f"{context}: Параграф удален (стал пустым после фильтрации)"
                        )
            else:
                filtered_chapter["paragraphs"].append(filtered_text)
        
        return filtered_chapter
    
    def process_all_translations(self):
        """Обрабатывает все файлы переводов"""
        print("\n🔍 Пост-процессинг переводов")
        print("=" * 60)
        
        # Находим все файлы переводов
        translation_files = sorted(self.input_dir.glob("*_translated.json"))
        
        if not translation_files:
            print(f"❌ Не найдено файлов переводов в {self.input_dir}")
            return False
        
        print(f"📚 Найдено глав для обработки: {len(translation_files)}")
        print(f"📋 Загружен черный список:")
        print(f"   • Фраз: {len(self.config['blacklist'].get('phrases', []))}")
        print(f"   • Символов: {len(self.config['blacklist'].get('symbols', []))}")
        print(f"   • Паттернов: {len(self.config['blacklist'].get('patterns', []))}")
        print()
        
        # Обрабатываем каждую главу
        with tqdm(total=len(translation_files), desc="Обработка глав") as pbar:
            for file_path in translation_files:
                # Загружаем данные главы
                with open(file_path, 'r', encoding='utf-8') as f:
                    chapter_data = json.load(f)
                
                # Обрабатываем главу
                filtered_chapter = self.process_chapter(
                    chapter_data, 
                    file_path.stem
                )
                
                # Сохраняем отфильтрованную главу
                output_file = self.output_dir / file_path.name
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(filtered_chapter, f, ensure_ascii=False, indent=2)
                
                pbar.update(1)
        
        # Сохраняем лог
        if self.config["settings"]["log_removals"] and self.log_entries:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"Лог пост-процессинга от {datetime.now().isoformat()}\n")
                f.write("=" * 60 + "\n\n")
                for entry in self.log_entries:
                    f.write(entry + "\n")
        
        return True
    
    def print_statistics(self):
        """Выводит статистику обработки"""
        print("\n📊 Статистика пост-процессинга:")
        print("=" * 60)
        print(f"📚 Обработано глав: {self.stats['total_chapters']}")
        print(f"📝 Обработано параграфов: {self.stats['total_paragraphs']}")
        print(f"✏️ Изменено параграфов: {self.stats['modified_paragraphs']}")
        print(f"🗑️ Удалено пустых параграфов: {self.stats['removed_paragraphs']}")
        
        if self.stats["removed_symbols"]:
            print("\n🔤 Удаленные символы:")
            for symbol, count in sorted(self.stats["removed_symbols"].items()):
                print(f"   • '{symbol}': {count} раз")
        
        if self.stats["removed_phrases"]:
            print("\n📝 Удаленные фразы:")
            for phrase, count in sorted(self.stats["removed_phrases"].items()):
                print(f"   • '{phrase[:50]}...': {count} раз" if len(phrase) > 50 
                      else f"   • '{phrase}': {count} раз")
        
        if self.stats["removed_patterns"]:
            print("\n🔍 Удаленные паттерны:")
            for pattern, count in sorted(self.stats["removed_patterns"].items()):
                print(f"   • {pattern}: {count} раз")
        
        if self.log_entries and self.config["settings"]["log_removals"]:
            print(f"\n📋 Подробный лог сохранен в: {self.log_file}")
    
    def backup_original(self):
        """Создает резервную копию оригинальных переводов"""
        backup_dir = self.input_dir.parent / f"{self.input_dir.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n💾 Создание резервной копии в {backup_dir}...")
        shutil.copytree(self.input_dir, backup_dir)
        print(f"✅ Резервная копия создана")
        
        return backup_dir

def main():
    """Основная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Пост-процессинг переведенного текста с фильтрацией по черному списку'
    )
    parser.add_argument(
        '--config',
        default='blacklist_config.json',
        help='Путь к файлу конфигурации (по умолчанию: blacklist_config.json)'
    )
    parser.add_argument(
        '--input-dir',
        default='translations',
        help='Директория с исходными переводами (по умолчанию: translations)'
    )
    parser.add_argument(
        '--output-dir',
        default='translations_filtered',
        help='Директория для отфильтрованных переводов (по умолчанию: translations_filtered)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Не создавать резервную копию оригинальных файлов'
    )
    parser.add_argument(
        '--replace',
        action='store_true',
        help='Заменить оригинальные файлы отфильтрованными'
    )
    
    args = parser.parse_args()
    
    # Создаем процессор
    processor = TranslationPostProcessor(
        config_file=args.config,
        input_dir=args.input_dir,
        output_dir=args.output_dir
    )
    
    # Создаем резервную копию если нужно
    if not args.no_backup and args.replace:
        processor.backup_original()
    
    # Обрабатываем переводы
    success = processor.process_all_translations()
    
    if success:
        # Выводим статистику
        processor.print_statistics()
        
        # Заменяем оригинальные файлы если указано
        if args.replace:
            print(f"\n🔄 Замена оригинальных файлов...")
            
            # Удаляем старую директорию
            shutil.rmtree(args.input_dir)
            
            # Переименовываем новую
            Path(args.output_dir).rename(args.input_dir)
            
            print(f"✅ Файлы заменены")
        else:
            print(f"\n✅ Отфильтрованные переводы сохранены в: {args.output_dir}")
    else:
        print("\n❌ Ошибка при обработке")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())