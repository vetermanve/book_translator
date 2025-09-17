#!/usr/bin/env python3
"""
Генерация фонетических транскрипций для английских терминов через DeepSeek API
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List
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


class PhoneticGenerator:
    def __init__(self, api_key: str = None):
        """Инициализация генератора фонетических транскрипций"""
        self.translator = DeepSeekTranslator(api_key)
        
        # Базовые примеры для обучения модели
        self.examples = {
            # Аббревиатуры
            'CMMI': 'си-эм-эм-ай',
            'SEI': 'эс-и-ай',
            'API': 'эй-пи-ай',
            'URL': 'ю-ар-эл',
            'HTML': 'эйч-ти-эм-эл',
            
            # Составные термины
            'Process Area': 'про́цесс э́риа',
            'Maturity Level': 'мэтью́рити ле́вел',
            'Software Engineering': 'со́фтвер энжини́ринг',
            
            # Отдельные слова
            'Development': 'девело́пмент',
            'Services': 'сёрвисез',
            'Agile': 'э́джайл',
            'Level': 'левел',
            
            # С точками
            'C.M.M.I.': 'си-эм-эм-ай',
            'U.S.A.': 'ю-эс-эй'
        }
        
    def create_phonetic_prompt(self, terms: List[str]) -> str:
        """Создает промпт для генерации фонетических транскрипций"""
        examples_text = "\n".join([
            f"{en}: {ru}" 
            for en, ru in list(self.examples.items())[:10]
        ])
        
        terms_text = "\n".join(terms)
        
        prompt = f"""Создай фонетическую транскрипцию на русском языке для следующих английских терминов.
Транскрипция должна помочь правильному произношению при чтении вслух синтезатором речи.

Правила:
1. Для аббревиатур - произносить по буквам через дефис (FBI → эф-би-ай)
2. Для слов - фонетическая запись кириллицей с ударениями (Development → девело́пмент)
3. Для составных терминов - транскрипция каждого слова (Process Area → про́цесс э́риа)
4. Использовать ударения где нужно (знак ́ после ударной гласной)

Примеры:
{examples_text}

Термины для транскрипции:
{terms_text}

Формат ответа - JSON объект, где ключ - оригинальный термин, значение - транскрипция:
{{"термин": "транскрипция"}}"""
        
        return prompt
    
    def generate_batch(self, terms: List[str], batch_size: int = 20) -> Dict[str, str]:
        """Генерирует транскрипции для пачки терминов"""
        if not terms:
            return {}
        
        # Ограничиваем размер батча
        terms_batch = terms[:batch_size]
        
        prompt = self.create_phonetic_prompt(terms_batch)
        
        try:
            response = self.translator.translate_text(
                prompt,
                system_message="Ты - эксперт по фонетике и транскрипции. Создаешь точные фонетические транскрипции английских терминов на русский язык для синтезаторов речи.",
                temperature=0.3,
                max_tokens=2000
            )
            
            # Пытаемся распарсить JSON из ответа
            try:
                # Ищем JSON в ответе
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_text = response[json_start:json_end]
                    return json.loads(json_text)
                else:
                    print(f"⚠️ Не найден JSON в ответе")
                    return {}
            except json.JSONDecodeError as e:
                print(f"⚠️ Ошибка парсинга JSON: {e}")
                # Пытаемся извлечь вручную
                return self.parse_manual_response(response, terms_batch)
                
        except Exception as e:
            print(f"❌ Ошибка при генерации: {e}")
            return {}
    
    def parse_manual_response(self, response: str, terms: List[str]) -> Dict[str, str]:
        """Парсит ответ вручную, если JSON не удался"""
        result = {}
        lines = response.split('\n')
        
        for line in lines:
            for term in terms:
                if term in line:
                    # Ищем паттерн "term: transcription" или "term → transcription"
                    for sep in [':', '→', '-', '—']:
                        if sep in line:
                            parts = line.split(sep, 1)
                            if len(parts) == 2:
                                key = parts[0].strip().strip('"\'')
                                value = parts[1].strip().strip('"\'')
                                if term in key:
                                    result[term] = value
                                    break
        
        return result
    
    def generate_all(self, terms_file: str = "extracted_terms.json", 
                    batch_size: int = 20, workers: int = 5):
        """Генерирует транскрипции для всех терминов из файла"""
        
        # Загружаем термины
        with open(terms_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Собираем все уникальные термины
        all_terms = set()
        for term_type, terms_list in data.get('terms_by_type', {}).items():
            all_terms.update(terms_list)
        
        # Убираем термины, для которых уже есть транскрипции
        terms_to_process = [t for t in all_terms if t not in self.examples]
        
        print(f"📝 Всего терминов: {len(all_terms)}")
        print(f"🔄 Нужно обработать: {len(terms_to_process)}")
        
        if not terms_to_process:
            print("✅ Все термины уже имеют транскрипции")
            return self.examples
        
        # Разбиваем на батчи
        batches = []
        for i in range(0, len(terms_to_process), batch_size):
            batch = terms_to_process[i:i+batch_size]
            batches.append(batch)
        
        print(f"📦 Батчей для обработки: {len(batches)}")
        
        # Результаты
        all_phonetics = dict(self.examples)  # Начинаем с известных
        
        # Обрабатываем батчи параллельно
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.generate_batch, batch): batch 
                for batch in batches
            }
            
            with tqdm(total=len(batches), desc="Генерация транскрипций") as pbar:
                for future in as_completed(futures):
                    batch = futures[future]
                    try:
                        result = future.result()
                        all_phonetics.update(result)
                        pbar.update(1)
                        
                        # Показываем примеры
                        if result:
                            example = list(result.items())[0]
                            print(f"  ✓ {example[0]} → {example[1]}")
                            
                    except Exception as e:
                        print(f"❌ Ошибка обработки батча: {e}")
                        pbar.update(1)
                    
                    # Небольшая пауза между запросами
                    time.sleep(0.5)
        
        return all_phonetics
    
    def save_phonetics(self, phonetics: Dict[str, str], output_file: str = "phonetics.json"):
        """Сохраняет фонетические транскрипции в файл"""
        # Сортируем по алфавиту
        sorted_phonetics = dict(sorted(phonetics.items()))
        
        # Добавляем метаданные
        output = {
            "version": "1.0",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_terms": len(phonetics),
            "phonetics": sorted_phonetics,
            "statistics": {
                "abbreviations": len([k for k in phonetics.keys() if k.isupper()]),
                "compound_terms": len([k for k in phonetics.keys() if ' ' in k]),
                "single_words": len([k for k in phonetics.keys() if ' ' not in k and not k.isupper()])
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 Сохранено в: {output_file}")
        return output


def main():
    parser = argparse.ArgumentParser(description='Генерация фонетических транскрипций через DeepSeek')
    parser.add_argument('--terms', default='extracted_terms.json',
                       help='Файл с извлеченными терминами')
    parser.add_argument('--output', default='phonetics.json',
                       help='Файл для сохранения транскрипций')
    parser.add_argument('--batch-size', type=int, default=20,
                       help='Размер батча для обработки')
    parser.add_argument('--workers', type=int, default=5,
                       help='Количество параллельных потоков')
    parser.add_argument('--api-key', help='DeepSeek API ключ')
    
    args = parser.parse_args()
    
    print("🎯 Генерация фонетических транскрипций через DeepSeek")
    print("=" * 60)
    
    # Проверяем наличие файла с терминами
    if not Path(args.terms).exists():
        print(f"❌ Файл {args.terms} не найден!")
        print("   Сначала запустите: python3 07_extract_terms.py")
        return
    
    # Получаем API ключ
    api_key = args.api_key or os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ API ключ не найден!")
        print("   Установите DEEPSEEK_API_KEY или используйте --api-key")
        return
    
    # Создаем генератор
    generator = PhoneticGenerator(api_key)
    
    # Генерируем транскрипции
    phonetics = generator.generate_all(
        args.terms,
        batch_size=args.batch_size,
        workers=args.workers
    )
    
    # Сохраняем результаты
    output_data = generator.save_phonetics(phonetics, args.output)
    
    # Статистика
    print(f"\n📊 Статистика:")
    print(f"  • Всего терминов: {output_data['total_terms']}")
    print(f"  • Аббревиатур: {output_data['statistics']['abbreviations']}")
    print(f"  • Составных терминов: {output_data['statistics']['compound_terms']}")
    print(f"  • Отдельных слов: {output_data['statistics']['single_words']}")
    
    print("\n✅ Готово!")
    print(f"\n💡 Теперь можно использовать в аудиокниге:")
    print(f"   python3 05_create_audiobook.py --phonetics {args.output}")


if __name__ == "__main__":
    main()