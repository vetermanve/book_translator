#!/usr/bin/env python3
"""
Автоматический анализатор контекста для определения типа текста и настроек перевода
"""

import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
from deepseek_translator import DeepSeekTranslator

class ContextAnalyzer:
    def __init__(self):
        self.translator = DeepSeekTranslator()
        self.context_file = Path('translation_context.yaml')
        self.analysis_cache = Path('context/analysis_cache.json')
        self.analysis_cache.parent.mkdir(exist_ok=True)
        
        # Словари для определения типа текста
        self.technical_markers = {
            'it': ['software', 'code', 'algorithm', 'database', 'API', 'framework', 
                   'programming', 'development', 'deploy', 'server', 'backend', 'frontend'],
            'engineering': ['design', 'specification', 'requirement', 'system', 'architecture',
                           'component', 'module', 'interface', 'implementation'],
            'management': ['employee', 'worker', 'manager', 'organization', 'workplace',
                          'motivation', 'satisfaction', 'engagement', 'productivity',
                          'leadership', 'team', 'performance', 'job', 'career'],
            'psychology': ['behavior', 'motivation', 'satisfaction', 'engagement', 'meaning',
                          'psychology', 'attitude', 'human nature', 'perception'],
            'business': ['company', 'CEO', 'profit', 'market', 'customer', 'strategy',
                        'revenue', 'business', 'corporation', 'enterprise', 'industry'],
            'science': ['research', 'hypothesis', 'experiment', 'analysis', 'data', 
                       'methodology', 'results', 'conclusion', 'theory']
        }
        
        self.style_indicators = {
            'formal': ['therefore', 'furthermore', 'consequently', 'nevertheless', 
                      'whereas', 'hereby', 'pursuant'],
            'informal': ["let's", "you'll", "we'll", "don't", "won't", "can't", 
                        'gonna', 'wanna', 'kinda'],
            'academic': ['abstract', 'methodology', 'literature review', 'hypothesis',
                        'conclusion', 'references', 'citation', 'et al.'],
            'instructional': ['step 1', 'step 2', 'how to', 'tutorial', 'guide',
                             'follow these', 'make sure', 'be careful']
        }
    
    def analyze_text_sample(self, text: str, sample_size: int = 5000) -> Dict:
        """Анализирует образец текста для определения его характеристик"""
        
        # Берем образец текста
        sample = text[:sample_size] if len(text) > sample_size else text
        
        # Базовая статистика
        words = sample.lower().split()
        word_count = len(words)
        sentences = re.split(r'[.!?]+', sample)
        avg_sentence_length = len(words) / max(len(sentences), 1)
        
        # Определяем тип текста
        text_type = self._detect_text_type(sample)
        
        # Определяем область знаний
        domain = self._detect_domain(sample, words)
        
        # Определяем стиль
        style = self._detect_style(sample, words, avg_sentence_length)
        
        # Определяем технический уровень
        tech_level = self._detect_technical_level(sample, words)
        
        return {
            'text_type': text_type,
            'domain': domain,
            'style': style,
            'technical_level': tech_level,
            'statistics': {
                'word_count': word_count,
                'avg_sentence_length': avg_sentence_length,
                'unique_words': len(set(words)),
                'lexical_diversity': len(set(words)) / word_count if word_count > 0 else 0
            }
        }
    
    def _detect_text_type(self, text: str) -> str:
        """Определяет тип текста"""
        
        text_lower = text.lower()
        
        # Проверка на книгу о менеджменте/работе
        work_psychology_markers = ['work', 'worker', 'employee', 'job', 'satisfaction', 
                                  'engagement', 'motivation', 'workplace', 'organization']
        work_count = sum(1 for marker in work_psychology_markers if marker in text_lower)
        
        # Если много терминов о работе - это бизнес-литература
        if work_count >= 4:
            return 'business'  # Бизнес-литература о работе и мотивации
        
        # Проверка на академический текст
        academic_markers = ['abstract', 'references', 'doi:', 'isbn', 'et al', 'journal']
        if any(marker in text_lower for marker in academic_markers):
            return 'academic'
        
        # Проверка исследований и статистики (Gallup и т.д.)
        if all(marker in text_lower for marker in ['research', 'percent', 'data']):
            if work_count > 3:
                return 'business'  # Бизнес-исследование
            return 'academic'
        
        # Проверка на художественный текст  
        if 'chapter' in text_lower and work_count < 3:
            if '"' in text or '"' in text:  # Есть диалоги
                return 'fiction'
        
        # Проверка на юридический текст
        if any(marker in text_lower for marker in ['whereas', 'pursuant', 'hereby', 'clause']):
            return 'legal'
        
        # Проверка на медицинский текст
        if all(marker in text_lower for marker in ['patient', 'hospital', 'medical']):
            if 'custodian' not in text_lower:  # Исключаем истории о работниках больниц
                return 'medical'
        
        # Проверка на бизнес текст по дополнительным маркерам
        business_markers = ['CEO', 'company', 'business', 'management', 'employee']
        if sum(1 for marker in business_markers if marker in text) >= 3:
            return 'business'
        
        # Проверка на технический текст
        tech_words = re.findall(r'\b[A-Z]{2,}\b', text)  # Аббревиатуры
        if len(tech_words) > 10 and work_count < 3:
            return 'technical'
        
        return 'general'
    
    def _detect_domain(self, text: str, words: List[str]) -> str:
        """Определяет область знаний"""
        
        domain_scores = {}
        for domain, markers in self.technical_markers.items():
            score = sum(1 for word in words if word in markers)
            if score > 0:
                domain_scores[domain] = score
        
        # Объединяем management и psychology если оба высокие
        if 'management' in domain_scores and 'psychology' in domain_scores:
            if domain_scores['management'] > 3 or domain_scores['psychology'] > 2:
                return 'management'  # Организационная психология относится к менеджменту
        
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return 'general'
    
    def _detect_style(self, text: str, words: List[str], avg_sentence_length: float) -> Dict:
        """Определяет стиль текста"""
        
        # Формальность
        formal_score = sum(1 for word in words if word in self.style_indicators['formal'])
        informal_score = sum(1 for word in words if word in self.style_indicators['informal'])
        
        if formal_score > informal_score * 2:
            formality = 'formal'
        elif informal_score > formal_score * 2:
            formality = 'informal'
        else:
            formality = 'neutral'
        
        # Тон
        if any(word in words for word in self.style_indicators['academic']):
            tone = 'academic'
        elif any(word in words for word in self.style_indicators['instructional']):
            tone = 'instructional'
        elif avg_sentence_length < 15:
            tone = 'conversational'
        else:
            tone = 'neutral'
        
        # Аудитория
        technical_terms = len([w for w in words if len(w) > 10])
        if technical_terms / len(words) > 0.1:
            audience = 'specialists'
        elif formality == 'informal':
            audience = 'general'
        else:
            audience = 'professionals'
        
        return {
            'formality': formality,
            'tone': tone,
            'audience': audience
        }
    
    def _detect_technical_level(self, text: str, words: List[str]) -> str:
        """Определяет технический уровень текста"""
        
        # Подсчет технических индикаторов
        acronyms = len(re.findall(r'\b[A-Z]{2,}\b', text))
        long_words = len([w for w in words if len(w) > 12])
        special_chars = len(re.findall(r'[=<>≤≥∈∀∃\[\]{}()]', text))
        
        tech_score = acronyms + long_words/10 + special_chars/5
        
        if tech_score > 50:
            return 'high'
        elif tech_score > 20:
            return 'medium'
        else:
            return 'low'
    
    def analyze_with_ai(self, text_sample: str) -> Dict:
        """Использует AI для более точного анализа контекста"""
        
        prompt = f"""Проанализируй следующий текст и определи его характеристики.

Текст (первые 2000 символов):
{text_sample[:2000]}

Определи:
1. Тип текста (technical/fiction/academic/business/legal/medical/general)
2. Область знаний (it/engineering/management/science/humanities/general)
3. Формальность (formal/informal/neutral)
4. Целевая аудитория (specialists/professionals/students/general)
5. Основная тематика (одним предложением)
6. Рекомендуемый стиль перевода

Ответь в формате JSON:
{{
    "text_type": "...",
    "domain": "...",
    "formality": "...",
    "audience": "...",
    "topic": "...",
    "translation_style": "..."
}}"""

        try:
            response = self.translator.translate_text(
                prompt,
                system_message="Ты эксперт по анализу текстов и лингвистике.",
                temperature=0.3
            )
            
            # Пытаемся извлечь JSON из ответа
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Ошибка AI анализа: {e}")
        
        return {}
    
    def generate_context_config(self, analysis: Dict) -> Dict:
        """Генерирует конфигурацию контекста на основе анализа"""
        
        config = {
            'text_type': analysis.get('text_type', 'general'),
            'domain': analysis.get('domain', 'general'),
            'style': analysis.get('style', {
                'formality': 'neutral',
                'audience': 'general',
                'tone': 'neutral'
            }),
            'technical_level': analysis.get('technical_level', 'medium')
        }
        
        # Генерируем системный промпт на основе анализа
        config['system_prompt'] = self._generate_system_prompt(config)
        
        # Добавляем специфические настройки
        if config['text_type'] == 'technical':
            config['processing'] = {
                'preserve_terms': True,
                'use_russian_terms': True,
                'preserve_placeholders': True,
                'preserve_formatting': True
            }
        elif config['text_type'] == 'fiction':
            config['processing'] = {
                'preserve_names': True,
                'adapt_idioms': True,
                'literary_style': True
            }
        elif config['text_type'] == 'academic':
            config['processing'] = {
                'strict_terminology': True,
                'preserve_citations': True,
                'formal_style': True
            }
        
        return config
    
    def _generate_system_prompt(self, config: Dict) -> str:
        """Генерирует системный промпт на основе конфигурации"""
        
        # Базовый промпт
        prompt_parts = ["Ты профессиональный переводчик с английского на русский язык."]
        
        # Добавляем специализацию
        if config['domain'] == 'it':
            prompt_parts.append("Специализация: IT и разработка программного обеспечения.")
            prompt_parts.append("Используй современную российскую IT-терминологию.")
        elif config['domain'] == 'engineering':
            prompt_parts.append("Специализация: инженерные и технические тексты.")
            prompt_parts.append("Используй точную техническую терминологию.")
        elif config['domain'] == 'management':
            prompt_parts.append("Специализация: управление проектами и бизнес-процессы.")
            prompt_parts.append("Используй принятую в России бизнес-терминологию.")
        elif config['domain'] == 'science':
            prompt_parts.append("Специализация: научные и исследовательские тексты.")
            prompt_parts.append("Соблюдай научный стиль изложения.")
        
        # Добавляем стиль
        style = config.get('style', {})
        if style.get('formality') == 'formal':
            prompt_parts.append("Стиль: формальный, профессиональный.")
        elif style.get('formality') == 'informal':
            prompt_parts.append("Стиль: неформальный, разговорный.")
        
        # Добавляем аудиторию
        if style.get('audience') == 'specialists':
            prompt_parts.append("Аудитория: специалисты и эксперты в данной области.")
        elif style.get('audience') == 'students':
            prompt_parts.append("Аудитория: студенты и начинающие специалисты.")
        elif style.get('audience') == 'general':
            prompt_parts.append("Аудитория: широкий круг читателей.")
        
        # Добавляем общие правила
        prompt_parts.extend([
            "Сохраняй все плейсхолдеры вида [IMAGE_XXX], [TABLE_XXX] без изменений.",
            "Сохраняй структуру и форматирование текста.",
            "Переводи точно, но естественно для русского языка."
        ])
        
        return " ".join(prompt_parts)
    
    def analyze_book(self, book_path: str = None) -> Dict:
        """Анализирует всю книгу и создает контекст"""
        
        print("📚 Анализ контекста книги...")
        
        # Пытаемся найти файл с контентом
        if book_path is None:
            possible_paths = [
                'extracted_content.json',
                'chapters/chapter_000.json', 
                'book.txt'
            ]
            for path in possible_paths:
                if Path(path).exists():
                    book_path = path
                    break
        
        if book_path is None or not Path(book_path).exists():
            # Если нет извлеченных глав, читаем напрямую book.txt
            if Path('book.txt').exists():
                with open('book.txt', 'r', encoding='utf-8') as f:
                    full_sample = f.read()[:10000]  # Первые 10000 символов
            else:
                raise FileNotFoundError("Не найден файл с контентом книги")
        elif book_path.endswith('.txt'):
            with open(book_path, 'r', encoding='utf-8') as f:
                full_sample = f.read()[:10000]
        else:
            # Загружаем JSON
            with open(book_path, 'r', encoding='utf-8') as f:
                book_data = json.load(f)
            
            # Собираем образец текста из разных частей
            sample_texts = []
            
            # Если это файл главы
            if 'content' in book_data:
                for para in book_data.get('content', [])[:20]:  # Первые 20 параграфов
                    if isinstance(para, dict) and para.get('type') == 'text':
                        sample_texts.append(para.get('content', ''))
                    elif isinstance(para, str):
                        sample_texts.append(para)
            # Если это файл с главами
            elif 'chapters' in book_data:
                for chapter in book_data.get('chapters', [])[:3]:  # Первые 3 главы
                    for para in chapter.get('content', [])[:5]:  # Первые 5 параграфов
                        if para.get('type') == 'text':
                            sample_texts.append(para.get('content', ''))
            
            full_sample = '\n'.join(sample_texts)
        
        # Анализируем текст
        print("  🔍 Автоматический анализ...")
        auto_analysis = self.analyze_text_sample(full_sample)
        
        # Дополняем AI анализом если доступен API
        ai_analysis = {}
        if self.translator.api_key and self.translator.api_key != 'your_api_key_here':
            print("  🤖 AI анализ контекста...")
            ai_analysis = self.analyze_with_ai(full_sample)
        
        # Объединяем результаты
        final_analysis = {**auto_analysis, **ai_analysis}
        
        # Генерируем конфигурацию
        print("  ⚙️ Генерация конфигурации...")
        config = self.generate_context_config(final_analysis)
        
        # Сохраняем результаты
        with open(self.context_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        # Сохраняем кеш анализа
        with open(self.analysis_cache, 'w', encoding='utf-8') as f:
            json.dump({
                'analysis': final_analysis,
                'config': config,
                'timestamp': str(Path(book_path).stat().st_mtime)
            }, f, ensure_ascii=False, indent=2)
        
        return config
    
    def get_context(self) -> Dict:
        """Получает текущий контекст из файла или анализирует заново"""
        
        if self.context_file.exists():
            with open(self.context_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            return self.analyze_book()
    
    def update_translator_context(self, translator: DeepSeekTranslator) -> None:
        """Обновляет контекст в переводчике"""
        
        context = self.get_context()
        
        # Обновляем системный промпт переводчика
        if 'system_prompt' in context:
            # Monkey-patch метод для использования нового промпта
            original_create_prompt = translator._create_system_prompt
            
            def new_create_prompt(ctx):
                return context['system_prompt']
            
            translator._create_system_prompt = new_create_prompt
        
        print(f"✅ Контекст обновлен: {context.get('text_type', 'general')} / {context.get('domain', 'general')}")


def main():
    analyzer = ContextAnalyzer()
    
    print("=" * 60)
    print("📊 АНАЛИЗАТОР КОНТЕКСТА ПЕРЕВОДА")
    print("=" * 60)
    print()
    
    # Анализируем книгу
    config = analyzer.analyze_book()
    
    print()
    print("📋 РЕЗУЛЬТАТЫ АНАЛИЗА:")
    print("-" * 40)
    print(f"Тип текста: {config.get('text_type', 'неопределен')}")
    print(f"Область: {config.get('domain', 'общая')}")
    print(f"Стиль: {config.get('style', {}).get('formality', 'нейтральный')}")
    print(f"Аудитория: {config.get('style', {}).get('audience', 'общая')}")
    print(f"Технический уровень: {config.get('technical_level', 'средний')}")
    print()
    print("💾 Конфигурация сохранена в: translation_context.yaml")
    print("📝 Системный промпт обновлен для оптимального перевода")
    print()
    print("Теперь переводчик будет автоматически использовать")
    print("определенный контекст для более точного перевода!")


if __name__ == '__main__':
    main()