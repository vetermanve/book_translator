#!/usr/bin/env python3
"""
Фонетическая замена английских терминов для правильного произношения
Так как edge-tts не поддерживает SSML, используем транслитерацию
"""

import json
import re
from pathlib import Path
from typing import Dict, List

class PhoneticReplacer:
    def __init__(self):
        """Словарь фонетических замен для английских терминов"""
        self.replacements = {
            # Основные аббревиатуры CMMI
            'CMMI': 'си-эм-эм-ай',
            'SEI': 'эс-и-ай',
            'SCAMPI': 'скампи',
            'CMU': 'си-эм-ю',
            
            # Процессные области
            'CAR': 'си-эй-ар',
            'CM': 'си-эм',
            'DAR': 'ди-эй-ар',
            'IPM': 'ай-пи-эм',
            'MA': 'эм-эй',
            'OPD': 'оу-пи-ди',
            'OPF': 'оу-пи-эф',
            'OPM': 'оу-пи-эм',
            'OPP': 'оу-пи-пи',
            'OT': 'оу-ти',
            'PI': 'пи-ай',
            'PMC': 'пи-эм-си',
            'PP': 'пи-пи',
            'PPQA': 'пи-пи-кью-эй',
            'QPM': 'кью-пи-эм',
            'RD': 'ар-ди',
            'REQM': 'рек-эм',
            'RSKM': 'риск-эм',
            'SAM': 'сэм',
            
            # Термины
            'Process Area': 'про́цесс э́риа',
            'Process Areas': 'про́цесс э́риаз',
            'Maturity Level': 'мэтью́рити ле́вел',
            'Capability Level': 'кейпэби́лити ле́вел',
            'Generic Goal': 'джене́рик гоул',
            'Specific Goal': 'специ́фик гоул',
            'Generic Practice': 'джене́рик прэ́ктис',
            'Specific Practice': 'специ́фик прэ́ктис',
            'Generic Goals': 'джене́рик гоулз',
            'Specific Goals': 'специ́фик гоулз',
            
            # Организации
            'Software Engineering Institute': 'со́фтвер энжини́ринг и́нститьют',
            'Carnegie Mellon University': 'ка́рнеги ме́ллон юниве́рсити',
            'Carnegie Mellon': 'ка́рнеги ме́ллон',
            
            # Методологии
            'Agile': 'э́джайл',
            'Scrum': 'скрам',
            'DevOps': 'дев-опс',
            'Waterfall': 'во́терфол',
            
            # Версии
            'Version': 'вёршн',
            'Development': 'девело́пмент',
            'Acquisition': 'эквизи́шн',
            'Services': 'сёрвисез',
            
            # Уровни
            'Level 1': 'левел ван',
            'Level 2': 'левел ту',
            'Level 3': 'левел фри',
            'Level 4': 'левел фор',
            'Level 5': 'левел файв',
        }
        
        # Добавляем варианты с точками
        abbreviations = ['CMMI', 'SEI', 'CAR', 'CM', 'DAR', 'IPM', 'MA', 
                        'OPD', 'OPF', 'OPM', 'OPP', 'OT', 'PI', 'PMC', 
                        'PP', 'PPQA', 'QPM', 'RD', 'REQM', 'RSKM', 'SAM']
        
        for abbr in abbreviations:
            dotted = '.'.join(abbr) + '.'  # C.M.M.I.
            if dotted not in self.replacements:
                self.replacements[dotted] = self.replacements[abbr]
    
    def replace_in_text(self, text: str) -> str:
        """Заменяет английские термины на фонетическую транскрипцию"""
        result = text
        
        # Сортируем по длине (сначала длинные фразы)
        sorted_terms = sorted(self.replacements.items(), 
                            key=lambda x: len(x[0]), 
                            reverse=True)
        
        for term, phonetic in sorted_terms:
            # Используем границы слов для точного совпадения
            pattern = r'\b' + re.escape(term) + r'\b'
            result = re.sub(pattern, phonetic, result, flags=re.IGNORECASE)
        
        return result
    
    def process_file(self, input_file: Path, output_file: Path):
        """Обрабатывает JSON файл с переводом"""
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Обрабатываем заголовок
        if 'title' in data:
            data['title'] = self.replace_in_text(data['title'])
        
        # Обрабатываем параграфы
        if 'paragraphs' in data:
            data['paragraphs'] = [
                self.replace_in_text(p) if p and not p.startswith('[IMAGE_') else p
                for p in data['paragraphs']
            ]
        
        # Сохраняем
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def process_directory(self, input_dir: str = "translations", 
                         output_dir: str = "translations_phonetic"):
        """Обрабатывает все файлы переводов"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        files = list(input_path.glob("*_translated.json"))
        print(f"📚 Найдено файлов для обработки: {len(files)}")
        
        for file in files:
            output_file = output_path / file.name
            self.process_file(file, output_file)
            print(f"✅ Обработан: {file.name}")
        
        print(f"\n✅ Готово! Файлы с фонетической заменой в: {output_path}")
        return output_path

def test_replacements():
    """Тест фонетических замен"""
    replacer = PhoneticReplacer()
    
    test_texts = [
        "Модель CMMI включает процессные области OPD и OPF.",
        "Process Area определяет Maturity Level 3.",
        "Software Engineering Institute разработал SCAMPI.",
        "Generic Goals и Specific Practices в Agile."
    ]
    
    print("🧪 Тест фонетических замен:")
    print("=" * 60)
    
    for text in test_texts:
        replaced = replacer.replace_in_text(text)
        print(f"\n📝 Исходный: {text}")
        print(f"🔄 Заменено: {replaced}")
    
    print("\n" + "=" * 60)
    print("Эти замены помогут edge-tts произносить термины правильно!")

if __name__ == "__main__":
    import sys
    
    if '--test' in sys.argv:
        test_replacements()
    else:
        print("🎙️ Фонетическая замена для правильного произношения")
        print("=" * 60)
        
        replacer = PhoneticReplacer()
        
        # Проверяем наличие переводов
        if Path("translations").exists():
            output_dir = replacer.process_directory()
            print(f"\n💡 Теперь используйте для генерации аудио:")
            print(f"   python3 05_create_audiobook.py --translations-dir {output_dir}")
        else:
            print("❌ Директория translations не найдена!")
            print("   Сначала выполните перевод книги")