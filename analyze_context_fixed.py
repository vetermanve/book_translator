#!/usr/bin/env python3
"""
Анализатор контекста с исправленным AI анализом для Ollama
"""

import json
import re
import yaml
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter

class ContextAnalyzerFixed:
    def __init__(self):
        self.context_file = Path('translation_context.yaml')
        self.analysis_cache = Path('context/analysis_cache.json')
        self.analysis_cache.parent.mkdir(exist_ok=True)
        
        # Настройки Ollama
        self.ollama_base = 'http://localhost:11434'
        self.model = 'llama3.2:3b'
        
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
    
    def call_ollama_directly(self, prompt: str) -> str:
        """Прямой вызов Ollama API без OpenAI клиента"""
        
        try:
            response = requests.post(
                f'{self.ollama_base}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'temperature': 0.1,
                    'options': {
                        'num_predict': 200,
                        'top_k': 10,
                        'top_p': 0.5
                    }
                },
                timeout=600  # 10 минут - ждём столько сколько нужно!
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"Ошибка Ollama: {response.status_code}")
                return ''
                
        except Exception as e:
            print(f"Ошибка вызова Ollama: {e}")
            return ''
    
    def analyze_with_ai(self, text_sample: str) -> Dict:
        """AI анализ через прямой вызов Ollama"""
        
        # Очень простой промпт для llama3.2:3b
        prompt = f"""Read this text: "{text_sample[:800]}"

This text discusses: work, employees, satisfaction, motivation, engagement in workplace.

What type of text is this? Choose one:
1. business (about work, management, organizations)
2. technical (about computers, programming)
3. academic (formal research paper)
4. fiction (story, novel)
5. general (other)

Answer with just the number (1, 2, 3, 4 or 5):"""
        
        print("🤖 Отправляем запрос к Ollama...")
        response = self.call_ollama_directly(prompt)
        
        if response:
            print(f"📝 Ответ получен: {response.strip()}")
            
            # Парсим простой ответ
            response_lower = response.lower().strip()
            
            # Определяем тип (может быть номер или слово)
            if '1' in response_lower or 'business' in response_lower or 'management' in response_lower or 'work' in response_lower:
                text_type = 'business'
                domain = 'management'
            elif '2' in response_lower or 'technical' in response_lower or 'computer' in response_lower:
                text_type = 'technical'
                domain = 'it'
            elif '3' in response_lower or 'academic' in response_lower or 'research' in response_lower:
                text_type = 'academic'
                domain = 'science'
            elif '4' in response_lower or 'fiction' in response_lower or 'story' in response_lower:
                text_type = 'fiction'
                domain = 'general'
            else:
                text_type = 'general'
                domain = 'general'
            
            # Теперь спросим про аудиторию
            audience_prompt = f"Who would read this {text_type} text? Answer with one word: managers, professionals, students, or general:"
            
            print("🤖 Определяем аудиторию...")
            audience_response = self.call_ollama_directly(audience_prompt)
            
            audience = 'professionals'  # По умолчанию
            if audience_response:
                print(f"📝 Аудитория: {audience_response.strip()}")
                if 'manager' in audience_response.lower():
                    audience = 'managers'
                elif 'student' in audience_response.lower():
                    audience = 'students'
                elif 'general' in audience_response.lower():
                    audience = 'general'
            
            result = {
                'text_type': text_type,
                'domain': domain,
                'audience': audience
            }
            
            print(f"✅ AI анализ завершен: {result}")
            return result
        
        return {}
    
    def analyze_text_sample(self, text: str, sample_size: int = 5000) -> Dict:
        """Базовый анализ текста"""
        
        sample = text[:sample_size] if len(text) > sample_size else text
        words = sample.lower().split()
        word_count = len(words)
        
        # Определяем тип текста
        text_lower = sample.lower()
        
        # Проверка на книгу о менеджменте/работе
        work_markers = ['work', 'worker', 'employee', 'job', 'satisfaction', 
                       'engagement', 'motivation', 'workplace', 'organization']
        work_count = sum(1 for marker in work_markers if marker in text_lower)
        
        if work_count >= 4:
            text_type = 'business'
        else:
            text_type = 'general'
        
        # Определяем область
        domain_scores = {}
        for domain, markers in self.technical_markers.items():
            score = sum(1 for word in words if word in markers)
            if score > 0:
                domain_scores[domain] = score
        
        if 'management' in domain_scores and 'psychology' in domain_scores:
            if domain_scores['management'] > 3 or domain_scores['psychology'] > 2:
                domain = 'management'
        elif domain_scores:
            domain = max(domain_scores, key=domain_scores.get)
        else:
            domain = 'general'
        
        return {
            'text_type': text_type,
            'domain': domain,
            'audience': 'professionals'
        }
    
    def generate_system_prompt(self, analysis: Dict) -> str:
        """Генерирует системный промпт на основе анализа"""
        
        prompt_parts = ["Ты профессиональный переводчик с английского на русский язык."]
        
        # Специализация по области
        if analysis.get('domain') == 'management':
            prompt_parts.append("Специализация: менеджмент и организационная психология.")
            prompt_parts.append("Используй принятую в России бизнес-терминологию.")
        elif analysis.get('domain') == 'it':
            prompt_parts.append("Специализация: IT и разработка ПО.")
            prompt_parts.append("Используй современную российскую IT-терминологию.")
        elif analysis.get('domain') == 'psychology':
            prompt_parts.append("Специализация: психология и поведение человека.")
            prompt_parts.append("Используй профессиональную психологическую терминологию.")
        
        # Стиль для типа текста
        if analysis.get('text_type') == 'business':
            prompt_parts.append("Текст: бизнес-литература с примерами и историями.")
            prompt_parts.append("Сохраняй живой стиль изложения, но используй профессиональную лексику.")
        elif analysis.get('text_type') == 'academic':
            prompt_parts.append("Текст: академическая литература.")
            prompt_parts.append("Используй формальный академический стиль.")
        
        # Аудитория
        if analysis.get('audience') == 'managers':
            prompt_parts.append("Аудитория: менеджеры и руководители.")
        elif analysis.get('audience') == 'professionals':
            prompt_parts.append("Аудитория: профессионалы в своей области.")
        
        # Общие правила
        prompt_parts.extend([
            "Сохраняй все плейсхолдеры [IMAGE_XXX], [TABLE_XXX] без изменений.",
            "Сохраняй структуру и форматирование текста.",
            "Переводи точно, но естественно для русского языка."
        ])
        
        return " ".join(prompt_parts)
    
    def analyze_and_save(self, text_path: str = 'book.txt') -> Dict:
        """Полный анализ с сохранением результатов"""
        
        print("📚 АНАЛИЗ КОНТЕКСТА")
        print("=" * 60)
        
        # Читаем текст
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()[:5000]
        
        # Базовый анализ
        print("\n1️⃣ Базовый анализ...")
        base_analysis = self.analyze_text_sample(text)
        print(f"   Тип: {base_analysis['text_type']}")
        print(f"   Область: {base_analysis['domain']}")
        
        # AI анализ
        print("\n2️⃣ AI анализ (llama3.2:3b)...")
        ai_analysis = self.analyze_with_ai(text)
        
        if ai_analysis:
            print(f"   Тип: {ai_analysis.get('text_type', '?')}")
            print(f"   Область: {ai_analysis.get('domain', '?')}")
            print(f"   Тема: {ai_analysis.get('topic', '?')}")
        
        # Комбинируем результаты (AI имеет приоритет если есть)
        final_analysis = {**base_analysis}
        if ai_analysis:
            final_analysis.update(ai_analysis)
        
        # Генерируем системный промпт
        system_prompt = self.generate_system_prompt(final_analysis)
        
        # Сохраняем конфигурацию
        config = {
            'text_type': final_analysis.get('text_type', 'general'),
            'domain': final_analysis.get('domain', 'general'),
            'style': {
                'formality': 'neutral',
                'tone': 'professional',
                'audience': final_analysis.get('audience', 'professionals')
            },
            'system_prompt': system_prompt
        }
        
        with open(self.context_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        
        print(f"\n✅ Сохранено в {self.context_file}")
        print(f"\n📝 Системный промпт:")
        print("-" * 40)
        print(system_prompt)
        
        return config


def main():
    analyzer = ContextAnalyzerFixed()
    analyzer.analyze_and_save()


if __name__ == '__main__':
    main()