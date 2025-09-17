import json
import os
from pathlib import Path
from datetime import datetime
import hashlib
from typing import List, Dict, Optional


class TranslationProgress:
    def __init__(self, progress_dir="progress"):
        self.progress_dir = Path(progress_dir)
        self.progress_dir.mkdir(exist_ok=True)
        self.progress_file = self.progress_dir / "translation_progress.json"
        self.progress = self._load_progress()
    
    def _load_progress(self):
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "chapters": {},
            "last_updated": None,
            "total_chapters": 0,
            "completed_chapters": 0,
            "current_chapter": None
        }
    
    def save_progress(self):
        self.progress["last_updated"] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)
    
    def mark_chapter_start(self, chapter_num):
        self.progress["current_chapter"] = chapter_num
        if str(chapter_num) not in self.progress["chapters"]:
            self.progress["chapters"][str(chapter_num)] = {
                "status": "in_progress",
                "started_at": datetime.now().isoformat(),
                "paragraphs_total": 0,
                "paragraphs_completed": 0
            }
        self.save_progress()
    
    def mark_chapter_complete(self, chapter_num):
        if str(chapter_num) in self.progress["chapters"]:
            self.progress["chapters"][str(chapter_num)]["status"] = "completed"
            self.progress["chapters"][str(chapter_num)]["completed_at"] = datetime.now().isoformat()
            self.progress["completed_chapters"] += 1
        self.save_progress()
    
    def is_chapter_translated(self, chapter_num):
        return (str(chapter_num) in self.progress["chapters"] and 
                self.progress["chapters"][str(chapter_num)]["status"] == "completed")


class ContextManager:
    def __init__(self, extracted_dir="extracted", context_dir="context"):
        self.extracted_dir = Path(extracted_dir)
        self.context_dir = Path(context_dir)
        self.context_dir.mkdir(exist_ok=True)
    
    def create_context_for_chapter(self, chapter_num):
        context = {
            "chapter": chapter_num,
            "previous_summary": "",
            "key_terms": {},
            "character_names": {},
            "style_notes": ""
        }
        
        if chapter_num > 0:
            prev_translated = self._get_previous_translated_summary(chapter_num - 1)
            if prev_translated:
                context["previous_summary"] = prev_translated
        
        context["style_notes"] = self._get_style_guide()
        
        if chapter_num > 0:
            context["key_terms"] = self._collect_key_terms(chapter_num - 1)
            context["character_names"] = self._collect_character_names(chapter_num - 1)
        
        context_file = self.context_dir / f"context_chapter_{chapter_num:03d}.json"
        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
        
        return context
    
    def load_chapter_context(self, chapter_num):
        """Загружает контекст главы"""
        context_file = self.context_dir / f"context_chapter_{chapter_num:03d}.json"
        if context_file.exists():
            with open(context_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def _get_previous_translated_summary(self, prev_chapter_num):
        translated_file = Path("translations") / f"chapter_{prev_chapter_num:03d}_translated.json"
        if translated_file.exists():
            with open(translated_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "summary" in data:
                    return data["summary"]
                
                text = " ".join(data.get("paragraphs", []))[:500]
                return f"Предыдущая глава: {text}..."
        return None
    
    def _get_style_guide(self):
        return """
        Руководство по стилю перевода:
        - Используйте современный IT-сленг, принятый в РФ
        - Термины: backend -> бэкенд, frontend -> фронтенд, deploy -> деплой, commit -> коммит
        - Сохраняйте технические термины без перевода там, где это уместно
        - Используйте "ты" вместо "вы" для неформального стиля
        - Сохраняйте оригинальные названия технологий (React, Docker, Kubernetes)
        - Адаптируйте идиомы к русскому контексту
        """
    
    def _collect_key_terms(self, prev_chapter_num):
        terms_file = self.context_dir / f"terms_chapter_{prev_chapter_num:03d}.json"
        if terms_file.exists():
            with open(terms_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _collect_character_names(self, prev_chapter_num):
        names_file = self.context_dir / f"names_chapter_{prev_chapter_num:03d}.json"
        if names_file.exists():
            with open(names_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_chapter_terms(self, chapter_num, terms):
        terms_file = self.context_dir / f"terms_chapter_{chapter_num:03d}.json"
        with open(terms_file, 'w', encoding='utf-8') as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)
    
    def save_chapter_names(self, chapter_num, names):
        names_file = self.context_dir / f"names_chapter_{chapter_num:03d}.json"
        with open(names_file, 'w', encoding='utf-8') as f:
            json.dump(names, f, ensure_ascii=False, indent=2)