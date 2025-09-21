#!/usr/bin/env python3
"""
Простой переводчик через Ollama API без OpenAI клиента
"""

import json
import requests
from pathlib import Path
from typing import Optional

class OllamaTranslator:
    def __init__(self):
        self.base_url = 'http://localhost:11434'
        self.model = 'llama3.1:8b'  # Или из .env
        
        # Загружаем настройки из .env
        env_settings = {}
        if Path('.env').exists():
            with open('.env') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, val = line.strip().split('=', 1)
                        env_settings[key] = val.strip('"\'')
        
        self.model = env_settings.get('OLLAMA_MODEL', self.model)
        self.temperature = float(env_settings.get('TEMPERATURE', '0.3'))
        
        # Загружаем контекст перевода
        self.system_prompt = self._load_system_prompt()
        
    def _load_system_prompt(self) -> str:
        """Загружает системный промпт из контекста"""
        try:
            import yaml
            with open('translation_context.yaml', 'r', encoding='utf-8') as f:
                context = yaml.safe_load(f)
                return context.get('system_prompt', 'Переведи на русский язык.')
        except:
            return """Ты профессиональный переводчик с английского на русский язык.
Специализация: менеджмент и организационная психология.
Используй принятую в России бизнес-терминологию.
Переводи точно и естественно."""
    
    def translate_text(self, text: str, max_tokens: int = 2000) -> Optional[str]:
        """Переводит текст через Ollama API напрямую"""
        
        prompt = f"""{self.system_prompt}

Переведи следующий текст, сохраняя все плейсхолдеры [IMAGE_XXX] без изменений:

{text}

Перевод:"""
        
        try:
            response = requests.post(
                f'{self.base_url}/api/generate',
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'temperature': self.temperature,
                    'options': {
                        'num_predict': max_tokens,
                        'top_p': 0.9,
                        'top_k': 40,
                        'repeat_penalty': 1.1
                    }
                },
                timeout=300  # 5 минут на перевод
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                print(f"Ошибка API: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            print("Таймаут при переводе")
            return None
        except Exception as e:
            print(f"Ошибка: {e}")
            return None
    
    def translate_paragraph_group(self, paragraphs: list, context: dict = None) -> list:
        """Переводит группу параграфов"""
        
        translated = []
        for para in paragraphs:
            if isinstance(para, dict):
                text = para.get('content', para.get('text', ''))
            else:
                text = str(para)
            
            if text.strip():
                translation = self.translate_text(text)
                if translation:
                    translated.append(translation)
                else:
                    # Возвращаем оригинал если перевод не удался
                    translated.append(text)
            else:
                translated.append('')
        
        return translated


# Для совместимости с существующим кодом
class DeepSeekTranslator(OllamaTranslator):
    """Алиас для совместимости"""
    pass