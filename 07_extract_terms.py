#!/usr/bin/env python3
"""
Извлечение английских терминов из переведенного текста
"""

import json
import re
from pathlib import Path
from collections import Counter
from typing import Dict, List, Set
import argparse

class TermExtractor:
    def __init__(self):
        """Инициализация экстрактора терминов"""
        # Паттерны для определения английских терминов
        self.patterns = [
            # Аббревиатуры (2+ заглавных букв)
            (r'\b[A-Z]{2,}\b', 'abbreviation'),
            
            # CamelCase термины
            (r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', 'camelcase'),
            
            # Термины с точками (C.M.M.I.)
            (r'\b[A-Z](?:\.[A-Z])+\.?\b', 'dotted'),
            
            # Level с числом
            (r'\bLevel\s+\d+\b', 'level'),
            
            # Составные термины (Process Area, Generic Goal)
            (r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', 'compound'),
            
            # Версии (v1.3, Version 1.3)
            (r'\b[Vv](?:ersion)?\s*\d+\.\d+\b', 'version'),
            
            # Отдельные английские слова в контексте русского текста
            (r'(?<=[а-яА-Я\s])[A-Za-z]+(?=[а-яА-Я\s])', 'english_word'),
        ]
        
        # Стоп-слова, которые не нужно считать терминами
        self.stop_words = {
            'Figure', 'Table', 'Chapter', 'Section', 'Page',
            'The', 'This', 'That', 'These', 'Those',
            'A', 'An', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For',
            'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'
        }
        
        # Известные термины CMMI для приоритетной обработки
        self.known_terms = {
            'CMMI', 'SEI', 'SCAMPI', 'CMU',
            'Process Area', 'Maturity Level', 'Capability Level',
            'Generic Goal', 'Specific Goal', 
            'Generic Practice', 'Specific Practice',
            'Generic Goals', 'Specific Goals',
            'CAR', 'CM', 'DAR', 'IPM', 'MA', 'OPD', 'OPF', 'OPM', 
            'OPP', 'OT', 'PI', 'PMC', 'PP', 'PPQA', 'QPM', 'RD', 
            'REQM', 'RSKM', 'SAM', 'TS', 'VAL', 'VER',
            'Software Engineering Institute',
            'Carnegie Mellon University',
            'Development', 'Acquisition', 'Services',
            'Agile', 'Scrum', 'DevOps', 'Waterfall',
            'High Maturity', 'Appraisal', 'Assessment'
        }
    
    def extract_from_text(self, text: str) -> Dict[str, Set[str]]:
        """Извлекает термины из текста по категориям"""
        terms_by_type = {}
        
        for pattern, term_type in self.patterns:
            matches = re.findall(pattern, text)
            # Фильтруем стоп-слова
            filtered = [m for m in matches if m not in self.stop_words]
            if filtered:
                if term_type not in terms_by_type:
                    terms_by_type[term_type] = set()
                terms_by_type[term_type].update(filtered)
        
        # Добавляем известные термины, если они есть в тексте
        known_found = set()
        for term in self.known_terms:
            if term in text:
                known_found.add(term)
        
        if known_found:
            terms_by_type['known'] = known_found
        
        return terms_by_type
    
    def extract_from_file(self, file_path: Path) -> Dict[str, Set[str]]:
        """Извлекает термины из JSON файла перевода"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        all_terms = {}
        
        # Обрабатываем заголовок
        if 'title' in data:
            terms = self.extract_from_text(data['title'])
            for term_type, term_set in terms.items():
                if term_type not in all_terms:
                    all_terms[term_type] = set()
                all_terms[term_type].update(term_set)
        
        # Обрабатываем параграфы
        if 'paragraphs' in data:
            for para in data['paragraphs']:
                if para and not para.startswith('[IMAGE_'):
                    terms = self.extract_from_text(para)
                    for term_type, term_set in terms.items():
                        if term_type not in all_terms:
                            all_terms[term_type] = set()
                        all_terms[term_type].update(term_set)
        
        return all_terms
    
    def extract_from_directory(self, input_dir: str = "translations"):
        """Извлекает все термины из директории переводов"""
        input_path = Path(input_dir)
        
        if not input_path.exists():
            print(f"❌ Директория {input_dir} не найдена")
            return None
        
        all_terms = {}
        term_frequency = Counter()
        
        files = list(input_path.glob("*_translated.json"))
        print(f"📚 Найдено файлов для анализа: {len(files)}")
        
        for file in files:
            file_terms = self.extract_from_file(file)
            
            # Объединяем термины
            for term_type, term_set in file_terms.items():
                if term_type not in all_terms:
                    all_terms[term_type] = set()
                all_terms[term_type].update(term_set)
                
                # Подсчитываем частоту
                for term in term_set:
                    term_frequency[term] += 1
        
        return all_terms, term_frequency
    
    def save_terms(self, all_terms: Dict, frequency: Counter, output_file: str = "extracted_terms.json"):
        """Сохраняет извлеченные термины в файл"""
        # Преобразуем sets в lists для JSON
        terms_list = {}
        for term_type, term_set in all_terms.items():
            terms_list[term_type] = sorted(list(term_set))
        
        # Топ частотных терминов
        top_frequent = dict(frequency.most_common(100))
        
        output = {
            "total_unique_terms": sum(len(terms) for terms in all_terms.values()),
            "terms_by_type": terms_list,
            "term_frequency": top_frequent,
            "statistics": {
                term_type: len(term_set) 
                for term_type, term_set in all_terms.items()
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        return output
    
    def print_statistics(self, all_terms: Dict, frequency: Counter):
        """Выводит статистику по терминам"""
        print("\n📊 Статистика извлеченных терминов:")
        print("=" * 60)
        
        total = sum(len(terms) for terms in all_terms.values())
        print(f"📝 Всего уникальных терминов: {total}")
        print()
        
        # По типам
        print("📂 По категориям:")
        for term_type, terms in all_terms.items():
            print(f"  • {term_type:15} : {len(terms):4} терминов")
        
        # Топ-20 частотных
        print("\n🔝 Топ-20 самых частых терминов:")
        for term, count in frequency.most_common(20):
            print(f"  {count:3}x - {term}")
        
        # Примеры по категориям
        print("\n📝 Примеры по категориям:")
        for term_type, terms in all_terms.items():
            examples = sorted(list(terms))[:5]
            print(f"\n  {term_type}:")
            for ex in examples:
                print(f"    • {ex}")


def main():
    parser = argparse.ArgumentParser(description='Извлечение английских терминов из переводов')
    parser.add_argument('--input-dir', default='translations',
                       help='Директория с переводами')
    parser.add_argument('--output', default='extracted_terms.json',
                       help='Файл для сохранения терминов')
    parser.add_argument('--min-frequency', type=int, default=2,
                       help='Минимальная частота для включения термина')
    
    args = parser.parse_args()
    
    print("🔍 Извлечение английских терминов из переводов")
    print("=" * 60)
    
    extractor = TermExtractor()
    
    # Извлекаем термины
    result = extractor.extract_from_directory(args.input_dir)
    
    if result:
        all_terms, frequency = result
        
        # Фильтруем по минимальной частоте
        if args.min_frequency > 1:
            filtered_terms = {}
            for term_type, terms in all_terms.items():
                filtered = {t for t in terms if frequency[t] >= args.min_frequency}
                if filtered:
                    filtered_terms[term_type] = filtered
            all_terms = filtered_terms
            print(f"\n🔎 Отфильтровано по частоте >= {args.min_frequency}")
        
        # Сохраняем результаты
        output_data = extractor.save_terms(all_terms, frequency, args.output)
        print(f"\n💾 Сохранено в: {args.output}")
        
        # Показываем статистику
        extractor.print_statistics(all_terms, frequency)
        
        print("\n✅ Готово!")
        print(f"\n💡 Следующий шаг:")
        print(f"   python3 08_generate_phonetics.py --terms {args.output}")
        
        return output_data


if __name__ == "__main__":
    main()