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
                timeout=600  # 10 минут на перевод
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
    
    def _create_system_prompt(self, context):
        """Для совместимости с 03_translate_parallel.py"""
        return self.system_prompt
    
    def _preserve_placeholders(self, text):
        """Для совместимости - просто возвращаем текст как есть"""
        return text
    
    def _group_paragraphs(self, paragraphs, max_chars=1500):
        """Группировка параграфов для эффективного перевода"""
        groups = []
        current_group = []
        current_length = 0
        image_placeholders = []  # Накапливаем плейсхолдеры
        
        for paragraph in paragraphs:
            # Если это плейсхолдер изображения - просто запоминаем его
            if paragraph.startswith("[IMAGE_"):
                image_placeholders.append(paragraph)
            else:
                # Если были накопленные изображения, добавляем их в текущую группу
                if image_placeholders:
                    current_group.extend(image_placeholders)
                    image_placeholders = []
                
                # Проверяем размер группы
                if current_length + len(paragraph) > max_chars and current_group:
                    # Сохраняем текущую группу
                    groups.append({
                        "text": "\n\n".join([p for p in current_group if not p.startswith("[IMAGE_")]),
                        "paragraphs": current_group,
                        "has_images": any(p.startswith("[IMAGE_") for p in current_group)
                    })
                    current_group = []
                    current_length = 0
                
                current_group.append(paragraph)
                current_length += len(paragraph)
        
        # Добавляем оставшиеся изображения к последней группе
        if image_placeholders:
            current_group.extend(image_placeholders)
        
        # Добавляем последнюю группу
        if current_group:
            groups.append({
                "text": "\n\n".join([p for p in current_group if not p.startswith("[IMAGE_")]),
                "paragraphs": current_group,
                "has_images": any(p.startswith("[IMAGE_") for p in current_group)
            })
        
        return groups


# Для совместимости с существующим кодом
class DeepSeekTranslator(OllamaTranslator):
    """Алиас для совместимости"""
    
    def __init__(self):
        super().__init__()
        # Добавляем атрибуты для совместимости
        self.api_key = 'ollama'  # Заглушка
        self.client = self  # Сам объект будет выступать как client
        self.chat = self  # Для client.chat
        self.completions = self  # Для client.chat.completions
    
    def _create_system_prompt(self, context):
        return self.system_prompt
    
    def _preserve_placeholders(self, text):
        return text
    
    def _group_paragraphs(self, paragraphs, max_chars=1500):
        """Наследуем метод из родительского класса"""
        return super()._group_paragraphs(paragraphs, max_chars)
    
    def create(self, **kwargs):
        """Эмуляция OpenAI API для совместимости с 03_translate_parallel.py"""
        messages = kwargs.get('messages', [])
        max_tokens = kwargs.get('max_tokens', 2000)
        
        # Извлекаем текст из messages
        user_message = ''
        for msg in messages:
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break
        
        # Переводим через Ollama
        translation = self.translate_text(user_message, max_tokens=max_tokens)
        
        # Возвращаем в формате OpenAI
        class FakeChoice:
            def __init__(self, content):
                self.message = type('Message', (), {'content': content})()
        
        class FakeResponse:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]
        
        return FakeResponse(translation if translation else '')
    
    def _restore_placeholders(self, text):
        """Для совместимости"""
        return text
    
    def _fallback_translate(self, text):
        """Запасной перевод"""
        return self.translate_text(text) or text
    
    def _translate_title(self, title):
        """Перевод заголовка"""
        return self.translate_text(title) or title
    
    def _generate_summary(self, paragraphs):
        """Генерация резюме главы"""
        text = '\n'.join(paragraphs[:3]) if len(paragraphs) > 3 else '\n'.join(paragraphs)
        prompt = f"Создай краткое резюме (2-3 предложения) следующего текста:\n\n{text}\n\nРезюме:"
        return self.translate_text(prompt, max_tokens=200) or "Резюме главы"
    
    def save_translation(self, chapter_num, translation):
        """Сохранение перевода"""
        output_dir = Path('translations')
        output_dir.mkdir(exist_ok=True)
        
        file_path = output_dir / f'chapter_{chapter_num:03d}.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(translation, f, ensure_ascii=False, indent=2)