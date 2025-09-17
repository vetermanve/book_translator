import json
import os
from pathlib import Path
import time
from typing import List, Dict
import re
from openai import OpenAI
# from dotenv import load_dotenv  # Убрано, читаем .env напрямую


class DeepSeekTranslator:
    def __init__(self, api_key=None):
        # Загружаем API ключ из .env файла
        if not api_key:
            env_file = Path('.env')
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('DEEPSEEK_API_KEY='):
                            # Получаем значение после =
                            value = line.split('=', 1)[1].strip()
                            # Убираем кавычки если есть
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            api_key = value
                            break
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if self.api_key:
            # DeepSeek использует OpenAI-совместимый API
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1"
            )
        else:
            self.client = None
            print("Предупреждение: DeepSeek API ключ не найден.")
        
        self.translations_dir = Path("translations")
        self.translations_dir.mkdir(exist_ok=True)
        
        # Специальные настройки для технического перевода
        self.tech_terms = {
            # Процессы и методологии
            "process": "процесс",
            "procedure": "процедура",
            "framework": "фреймворк",
            "methodology": "методология",
            "approach": "подход",
            "practice": "практика",
            "implementation": "реализация",
            "deployment": "развертывание",
            "integration": "интеграция",
            
            # CMMI специфичные термины
            "CMMI": "CMMI",
            "Capability Maturity Model": "Модель зрелости процессов",
            "maturity level": "уровень зрелости",
            "process area": "область процессов",
            "specific goal": "конкретная цель",
            "generic goal": "общая цель",
            "specific practice": "конкретная практика",
            "generic practice": "общая практика",
            
            # Разработка ПО
            "software": "программное обеспечение",
            "development": "разработка",
            "requirement": "требование",
            "design": "проектирование",
            "testing": "тестирование",
            "validation": "валидация",
            "verification": "верификация",
            "configuration": "конфигурация",
            "management": "управление",
            "quality": "качество",
            "assurance": "обеспечение",
            
            # Организационные термины
            "organization": "организация",
            "project": "проект",
            "team": "команда",
            "stakeholder": "заинтересованная сторона",
            "customer": "заказчик",
            "supplier": "поставщик",
            "performance": "производительность",
            "measurement": "измерение",
            "metric": "метрика",
            "indicator": "индикатор"
        }
    
    def translate_chapter(self, chapter_data, context, use_api=True):
        if use_api and self.client:
            return self._translate_with_deepseek(chapter_data, context)
        else:
            return self._translate_local(chapter_data, context)
    
    def _translate_with_deepseek(self, chapter_data, context):
        translated_paragraphs = []
        
        system_prompt = self._create_system_prompt(context)
        
        # Используем новую стратегию с контекстом: группы по 3 параграфа с контекстом
        paragraph_groups = self._group_paragraphs_with_context(chapter_data["paragraphs"], target_per_group=3)
        
        print(f"📝 Перевод главы '{chapter_data['title']}' ({len(paragraph_groups)} групп по 3 абзаца с контекстом)")
        
        for group_idx, paragraph_group in enumerate(paragraph_groups):
            # Если текста для перевода нет (только изображения)
            if not paragraph_group["translate_text"].strip():
                translated_paragraphs.extend(paragraph_group["to_translate"])
                continue
            
            # Формируем контекстный промпт
            context_prompt = self._build_context_prompt(paragraph_group)
            
            # Подготавливаем текст для перевода
            paragraph_with_placeholders = self._preserve_placeholders(paragraph_group["translate_text"])
            
            try:
                # Используем DeepSeek модель
                response = self.client.chat.completions.create(
                    model="deepseek-chat",  # Модель DeepSeek
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=3000
                )
                
                translated = response.choices[0].message.content
                translated = self._restore_placeholders(translated)
                translated = self._post_process_formatting(translated)
                
                # Разбиваем переведенный текст на параграфы
                translated_parts = translated.split('\n\n')
                
                # Восстанавливаем порядок с изображениями для текущей группы
                result_paragraphs = []
                text_idx = 0
                
                for original_paragraph in paragraph_group["to_translate"]:
                    if original_paragraph.startswith("[IMAGE_"):
                        # Вставляем изображение как есть
                        result_paragraphs.append(original_paragraph)
                    else:
                        # Вставляем переведенный текст
                        if text_idx < len(translated_parts):
                            result_paragraphs.append(translated_parts[text_idx])
                            text_idx += 1
                        else:
                            # Если переводов меньше чем оригиналов, используем запасной перевод
                            result_paragraphs.append(self._fallback_translate(original_paragraph))
                
                translated_paragraphs.extend(result_paragraphs)
                
                # Небольшая задержка между запросами
                time.sleep(0.5)  # Увеличиваем задержку для стабильности
                
            except Exception as e:
                print(f"⚠️  Ошибка при переводе группы {group_idx}: {e}")
                # При ошибке используем базовый перевод
                for p in paragraph_group["to_translate"]:
                    translated_paragraphs.append(self._fallback_translate(p))
        
        # Генерируем краткое содержание
        summary = self._generate_summary(translated_paragraphs)
        
        return {
            "number": chapter_data["number"],
            "title": self._translate_title(chapter_data["title"]),
            "paragraphs": translated_paragraphs,
            "summary": summary,
            "original_word_count": chapter_data["word_count"],
            "translator": "DeepSeek"
        }
    
    def translate_paragraph_group_with_context(self, paragraph_group, context):
        """Перевод одной группы параграфов с контекстом (для параллельного выполнения)"""
        if not self.client:
            # Fallback без API
            result_paragraphs = []
            for p in paragraph_group["to_translate"]:
                if p.startswith("[IMAGE_"):
                    result_paragraphs.append(p)
                else:
                    result_paragraphs.append(self._fallback_translate(p))
            return result_paragraphs
        
        try:
            system_prompt = self._create_system_prompt(context)
            context_prompt = self._build_context_prompt(paragraph_group)
            
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context_prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            
            translated = response.choices[0].message.content
            translated = self._restore_placeholders(translated)
            translated = self._post_process_formatting(translated)
            
            # Разбиваем переведенный текст на параграфы
            translated_parts = translated.split('\n\n')
            
            # Восстанавливаем порядок с изображениями
            result_paragraphs = []
            text_idx = 0
            
            for original_paragraph in paragraph_group["to_translate"]:
                if original_paragraph.startswith("[IMAGE_"):
                    result_paragraphs.append(original_paragraph)
                else:
                    if text_idx < len(translated_parts):
                        result_paragraphs.append(translated_parts[text_idx])
                        text_idx += 1
                    else:
                        result_paragraphs.append(self._fallback_translate(original_paragraph))
            
            return result_paragraphs
            
        except Exception as e:
            print(f"⚠️  Ошибка при переводе группы: {e}")
            # При ошибке используем базовый перевод
            result_paragraphs = []
            for p in paragraph_group["to_translate"]:
                if p.startswith("[IMAGE_"):
                    result_paragraphs.append(p)
                else:
                    result_paragraphs.append(self._fallback_translate(p))
            return result_paragraphs
    
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
    
    def _group_paragraphs_with_context(self, paragraphs, target_per_group=3):
        """Группировка параграфов с контекстом: 3 предыдущих + 3 для перевода + 3 следующих"""
        groups = []
        total_paragraphs = len(paragraphs)
        
        # Обрабатываем по target_per_group параграфов за раз
        for i in range(0, total_paragraphs, target_per_group):
            # Определяем диапазоны
            context_before_start = max(0, i - target_per_group)
            translate_start = i
            translate_end = min(i + target_per_group, total_paragraphs)
            context_after_end = min(translate_end + target_per_group, total_paragraphs)
            
            # Извлекаем части
            context_before = paragraphs[context_before_start:translate_start] if context_before_start < translate_start else []
            to_translate = paragraphs[translate_start:translate_end]
            context_after = paragraphs[translate_end:context_after_end] if translate_end < context_after_end else []
            
            # Фильтруем изображения из контекста (оставляем только в целевых параграфах)
            context_before_text = [p for p in context_before if not p.startswith("[IMAGE_")]
            context_after_text = [p for p in context_after if not p.startswith("[IMAGE_")]
            
            group = {
                "index": len(groups),
                "translate_start": translate_start,
                "translate_end": translate_end,
                "context_before": context_before_text,
                "to_translate": to_translate,
                "context_after": context_after_text,
                "translate_text": "\n\n".join([p for p in to_translate if not p.startswith("[IMAGE_")]),
                "has_images": any(p.startswith("[IMAGE_") for p in to_translate)
            }
            
            groups.append(group)
            
        return groups
    
    def _build_context_prompt(self, paragraph_group):
        """Создание промпта с контекстом из предыдущих и следующих абзацев"""
        parts = []
        
        if paragraph_group["context_before"]:
            parts.append("КОНТЕКСТ ПЕРЕД (НЕ ПЕРЕВОДИТЬ):")
            parts.append("\n\n".join(paragraph_group["context_before"][:2]))  # Ограничиваем контекст
            parts.append("")
        
        parts.append("ПЕРЕВЕДИ ЭТО:")
        parts.append(paragraph_group["translate_text"])
        
        if paragraph_group["context_after"]:
            parts.append("")
            parts.append("КОНТЕКСТ ПОСЛЕ (НЕ ПЕРЕВОДИТЬ):")
            parts.append("\n\n".join(paragraph_group["context_after"][:2]))  # Ограничиваем контекст
        
        return "\n".join(parts)
    
    def _create_system_prompt(self, context):
        prompt = f"""Переводчик CMMI документации EN→RU. Формальный технический стиль, российская IT-терминология.
Сохраняй: плейсхолдеры [IMAGE_XXX], форматирование, аббревиатуры CMMI/SCAMPI/SEI.
Контекст: {context.get('previous_summary', 'Начало документа')}"""
        
        return prompt
    
    def _preserve_placeholders(self, text):
        """Защита плейсхолдеров от изменения при переводе"""
        # Сохраняем оригинальные плейсхолдеры
        self._placeholder_map = {}
        placeholders = re.findall(r'\[IMAGE_[^\]]+\]', text)
        for i, placeholder in enumerate(placeholders):
            marker = f"<<<PLACEHOLDER_{i}>>>"
            self._placeholder_map[marker] = placeholder
            text = text.replace(placeholder, marker)
        return text
    
    def _restore_placeholders(self, text):
        """Восстановление плейсхолдеров после перевода"""
        # Восстанавливаем оригинальные плейсхолдеры из сохраненной карты
        if hasattr(self, '_placeholder_map'):
            for marker, original in self._placeholder_map.items():
                text = text.replace(marker, original)
        
        # Дополнительная обработка на случай изменений
        # Если DeepSeek вернул просто [IMAGE_0] вместо полного ID
        text = re.sub(r'\[IMAGE_(\d+)\]', lambda m: f'[IMAGE_{m.group(1)}]', text)
        # На случай если DeepSeek перевел слово IMAGE
        text = re.sub(r'\[ИЗОБРАЖЕНИЕ[_ ][^\]]+\]', lambda m: m.group(0).replace('ИЗОБРАЖЕНИЕ', 'IMAGE'), text)
        
        return text
    
    def _post_process_formatting(self, text):
        """Постобработка переведенного текста для сохранения форматирования"""
        # Удаляем лишние пробелы но сохраняем переносы строк
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Убираем пробелы в начале и конце строк
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        
        # Исправляем случаи где API мог потерять переносы между предложениями
        # Добавляем перенос перед заголовками (строки из 1-3 слов, заканчивающихся без точки)
        text = re.sub(r'([.!?])\s+([А-ЯA-Z][а-яa-z]{1,20}(?:\s+[А-ЯA-Z][а-яa-z]{1,20}){0,2})\s+([А-Я])', 
                     r'\1\n\n\2\n\3', text)
        
        # Добавляем переносы перед нумерованными списками
        text = re.sub(r'([.!?])\s+(\d+\.\s+[А-Я])', r'\1\n\n\2', text)
        
        # Добавляем переносы перед маркированными списками
        text = re.sub(r'([.!?])\s+([-•*]\s+[А-Я])', r'\1\n\n\2', text)
        
        # Убираем избыточные пустые строки (больше 3х подряд)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        return text.strip()
    
    def _translate_title(self, title):
        """Перевод заголовков глав"""
        translations = {
            "Chapter": "Глава",
            "Part": "Часть",
            "Section": "Раздел",
            "Introduction": "Введение",
            "Conclusion": "Заключение",
            "Preface": "Предисловие",
            "Appendix": "Приложение",
            "References": "Ссылки",
            "Glossary": "Глоссарий",
            "Index": "Индекс"
        }
        
        result = title
        for eng, rus in translations.items():
            result = result.replace(eng, rus)
        
        # Если это CMMI-специфичный заголовок, оставляем частично как есть
        if "CMMI" in result or "Process Area" in result:
            result = result.replace("Process Area", "Область процессов")
            result = result.replace("Generic Goals", "Общие цели")
            result = result.replace("Generic Practices", "Общие практики")
            result = result.replace("Specific Goals", "Конкретные цели")
            result = result.replace("Specific Practices", "Конкретные практики")
        
        return result
    
    def _fallback_translate(self, text):
        """Запасной вариант перевода при ошибке API"""
        if text.startswith("[IMAGE_"):
            return text
        
        # Базовый словарный перевод
        result = text
        for eng, rus in self.tech_terms.items():
            result = re.sub(r'\b' + eng + r'\b', rus, result, flags=re.IGNORECASE)
        
        return result
    
    def _translate_local(self, chapter_data, context):
        """Локальный перевод без API"""
        translated_paragraphs = []
        
        for paragraph in chapter_data["paragraphs"]:
            if paragraph.startswith("[IMAGE_"):
                translated_paragraphs.append(paragraph)
            else:
                translated = self._fallback_translate(paragraph)
                translated_paragraphs.append(translated)
        
        return {
            "number": chapter_data["number"],
            "title": self._translate_title(chapter_data["title"]),
            "paragraphs": translated_paragraphs,
            "summary": self._generate_simple_summary(translated_paragraphs),
            "original_word_count": chapter_data["word_count"],
            "translator": "Local"
        }
    
    def _generate_summary(self, paragraphs):
        """Генерация краткого содержания главы"""
        if not paragraphs:
            return ""
        
        # Берем первые несколько параграфов, исключая изображения
        text_paragraphs = [p for p in paragraphs[:5] if not p.startswith("[IMAGE_")]
        if text_paragraphs:
            summary = " ".join(text_paragraphs[:2])
            if len(summary) > 500:
                summary = summary[:500] + "..."
            return f"Краткое содержание: {summary}"
        
        return "Глава содержит преимущественно изображения и диаграммы"
    
    def _generate_simple_summary(self, paragraphs):
        """Простая генерация краткого содержания"""
        text_paragraphs = [p for p in paragraphs[:3] if not p.startswith("[IMAGE_")]
        if text_paragraphs:
            summary = " ".join(text_paragraphs[:1])
            if len(summary) > 300:
                summary = summary[:300] + "..."
            return summary
        return ""
    
    def save_translation(self, chapter_num, translation_data):
        """Сохранение переведенной главы"""
        filename = f"chapter_{chapter_num:03d}_translated.json"
        filepath = self.translations_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(translation_data, f, ensure_ascii=False, indent=2)
        
        return filepath