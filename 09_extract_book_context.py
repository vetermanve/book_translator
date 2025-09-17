#!/usr/bin/env python3
"""
Извлечение контекста книги для понимания основной темы и структуры
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


class BookContextExtractor:
    def __init__(self):
        """Инициализация экстрактора контекста"""
        self.context = {
            'title': '',
            'subtitle': '',
            'authors': [],
            'topics': [],
            'structure': {},
            'key_concepts': [],
            'target_audience': '',
            'book_purpose': '',
            'technical_level': '',
            'domain': ''
        }
    
    def extract_from_title_page(self, chapter_files: List[Path]) -> Dict:
        """Извлекает информацию из титульной страницы и введения"""
        # Обычно первые главы содержат важную контекстную информацию
        intro_text = ""
        
        for file in chapter_files[:3]:  # Первые 3 главы
            if file.exists():
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'title' in data:
                        # Анализируем заголовки
                        title = data['title']
                        if 'CMMI' in title or 'Maturity' in title:
                            self.context['domain'] = 'process_improvement'
                        
                        if not self.context['title'] and len(title) > 10:
                            self.context['title'] = title
                    
                    # Собираем первые параграфы для анализа
                    if 'paragraphs' in data:
                        for para in data['paragraphs'][:5]:
                            if para and not para.startswith('[IMAGE_'):
                                intro_text += para + "\n"
        
        return intro_text
    
    def extract_table_of_contents(self, chapter_files: List[Path]) -> List[Dict]:
        """Извлекает структуру книги из оглавления"""
        toc = []
        
        for file in chapter_files:
            if file.exists():
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    chapter_info = {
                        'file': file.name,
                        'title': data.get('title', ''),
                        'paragraphs_count': len(data.get('paragraphs', [])),
                        'has_images': any(p.startswith('[IMAGE_') for p in data.get('paragraphs', []))
                    }
                    toc.append(chapter_info)
        
        return toc
    
    def analyze_key_concepts(self, text: str) -> List[str]:
        """Анализирует ключевые концепции из текста"""
        concepts = []
        
        # Паттерны для поиска ключевых концепций
        patterns = [
            r'основн\w+ (концепци\w+|принцип\w+|идея\w*)',
            r'ключев\w+ (момент\w+|аспект\w+|элемент\w+)',
            r'важн\w+ (понимать|знать|учитывать)',
            r'цель\w* (книги|главы|раздела)',
            r'(определение|описание) \w+',
        ]
        
        # Известные термины для данной предметной области
        if 'CMMI' in text or 'матurity' in text.lower():
            concepts.extend([
                'процессная зрелость',
                'уровни зрелости',
                'процессные области',
                'непрерывное улучшение',
                'оценка процессов'
            ])
        
        return concepts
    
    def determine_technical_level(self, text: str) -> str:
        """Определяет технический уровень текста"""
        # Подсчет технических терминов
        technical_terms = len(re.findall(r'[A-Z]{2,}', text))
        formulas = len(re.findall(r'[=<>≤≥∈∀∃]', text))
        
        if technical_terms > 50 or formulas > 10:
            return "высокий"
        elif technical_terms > 20:
            return "средний"
        else:
            return "начальный"
    
    def generate_context_summary(self, extracted_dir: str = "extracted_fixed") -> Dict:
        """Генерирует полный контекст книги"""
        extracted_path = Path(extracted_dir)
        
        if not extracted_path.exists():
            print(f"❌ Директория {extracted_dir} не найдена")
            return None
        
        # Получаем список файлов глав
        chapter_files = sorted(extracted_path.glob("chapter_*.json"))
        
        if not chapter_files:
            print(f"❌ Не найдены файлы глав в {extracted_dir}")
            return None
        
        print(f"📚 Найдено {len(chapter_files)} глав для анализа")
        
        # Извлекаем информацию
        intro_text = self.extract_from_title_page(chapter_files)
        toc = self.extract_table_of_contents(chapter_files)
        
        # Анализируем
        self.context['structure'] = {
            'total_chapters': len(toc),
            'chapters': toc[:10],  # Первые 10 для примера
            'has_images': any(ch['has_images'] for ch in toc),
            'average_chapter_size': sum(ch['paragraphs_count'] for ch in toc) // len(toc)
        }
        
        self.context['key_concepts'] = self.analyze_key_concepts(intro_text)
        self.context['technical_level'] = self.determine_technical_level(intro_text)
        
        # Определяем целевую аудиторию на основе технического уровня
        if self.context['technical_level'] == "высокий":
            self.context['target_audience'] = "опытные специалисты и эксперты"
        elif self.context['technical_level'] == "средний":
            self.context['target_audience'] = "специалисты с базовыми знаниями"
        else:
            self.context['target_audience'] = "начинающие специалисты и студенты"
        
        # Формируем описание цели книги
        if 'CMMI' in intro_text:
            self.context['book_purpose'] = """
            Эта книга представляет модель CMMI для разработки программного обеспечения.
            Она помогает организациям улучшить процессы разработки, повысить качество
            продуктов и достичь более высоких уровней зрелости процессов.
            """
        
        return self.context
    
    def save_context(self, output_file: str = "book_context.json"):
        """Сохраняет извлеченный контекст в файл"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.context, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Контекст сохранен в: {output_file}")
        return self.context
    
    def print_context_summary(self):
        """Выводит краткую информацию о контексте"""
        print("\n📖 Контекст книги:")
        print("=" * 60)
        
        if self.context['title']:
            print(f"📚 Название: {self.context['title']}")
        
        print(f"🎯 Целевая аудитория: {self.context['target_audience']}")
        print(f"📊 Технический уровень: {self.context['technical_level']}")
        
        if self.context['domain']:
            print(f"🔬 Предметная область: {self.context['domain']}")
        
        if self.context['structure']:
            print(f"📂 Структура:")
            print(f"   • Глав: {self.context['structure']['total_chapters']}")
            print(f"   • Средний размер главы: {self.context['structure']['average_chapter_size']} параграфов")
            print(f"   • Содержит диаграммы: {'Да' if self.context['structure']['has_images'] else 'Нет'}")
        
        if self.context['key_concepts']:
            print(f"🔑 Ключевые концепции:")
            for concept in self.context['key_concepts'][:5]:
                print(f"   • {concept}")


def main():
    parser = argparse.ArgumentParser(description='Извлечение контекста книги')
    parser.add_argument('--input-dir', default='extracted_fixed',
                       help='Директория с извлеченными главами')
    parser.add_argument('--output', default='book_context.json',
                       help='Файл для сохранения контекста')
    
    args = parser.parse_args()
    
    print("🔍 Извлечение контекста книги")
    print("=" * 60)
    
    extractor = BookContextExtractor()
    
    # Генерируем контекст
    context = extractor.generate_context_summary(args.input_dir)
    
    if context:
        # Сохраняем
        extractor.save_context(args.output)
        
        # Показываем результаты
        extractor.print_context_summary()
        
        print("\n✅ Готово!")
        print(f"\n💡 Следующий шаг:")
        print(f"   python3 10_adapt_for_audio.py --context {args.output}")
    else:
        print("❌ Не удалось извлечь контекст")


if __name__ == "__main__":
    main()