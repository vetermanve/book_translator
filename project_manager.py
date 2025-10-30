#!/usr/bin/env python3

"""
Менеджер проектов для переводчика книг
Позволяет сохранять, восстанавливать и переключаться между проектами
"""

import os
import sys
import json
import shutil
import tarfile
from pathlib import Path
from datetime import datetime
import hashlib


class Colors:
    """ANSI цвета для консоли"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


class ProjectManager:
    """Менеджер проектов перевода книг"""
    
    def __init__(self):
        self.projects_dir = Path("projects_archive")
        self.projects_dir.mkdir(exist_ok=True)
        
        self.metadata_file = self.projects_dir / "projects.json"
        self.current_file = self.projects_dir / ".current"
        
        # Директории для сохранения
        self.work_dirs = [
            "extracted",
            "extracted_fixed", 
            "figures",
            "translations",
            "translations_fixed",
            "translations_formatted",
            "output",
            "context",
            "progress",
            "vectors",
            "images",
            "images_final",
            "audiobook",           # Аудиокниги v1.0
            "audio_adapted",       # Адаптированные тексты для аудио v2.0
            "audiobook_adapted",   # Аудиокниги v2.0
            "phonetics"            # Фонетические замены
        ]
        
        # Файлы для сохранения
        self.work_files = [
            "book.pdf",
            "USAGE.md",
            ".env",  # если есть настройки API
            "phonetics.json",  # фонетические замены
            "book_context.json"  # контекст книги для адаптации
        ]
        
        self.load_metadata()
    
    def load_metadata(self):
        """Загрузка метаданных проектов"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
        else:
            self.projects = {}
    
    def save_metadata(self):
        """Сохранение метаданных проектов"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)
    
    def get_book_hash(self, book_path):
        """Получение хеша книги для уникальной идентификации"""
        if not Path(book_path).exists():
            return None
        
        sha256_hash = hashlib.sha256()
        with open(book_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:12]
    
    def get_book_info(self, book_path="book.pdf"):
        """Извлечение информации о книге"""
        info = {
            "filename": Path(book_path).name,
            "size": 0,
            "pages": 0,
            "title": "",
            "hash": ""
        }
        
        if Path(book_path).exists():
            info["size"] = Path(book_path).stat().st_size
            info["hash"] = self.get_book_hash(book_path)
            
            # Пытаемся получить метаданные из PDF
            try:
                import fitz
                doc = fitz.open(book_path)
                info["pages"] = len(doc)
                metadata = doc.metadata
                if metadata:
                    info["title"] = metadata.get("title", "") or Path(book_path).stem
                doc.close()
            except:
                info["title"] = Path(book_path).stem
        
        return info
    
    def archive_project(self, project_name=None, description=""):
        """Архивирование текущего проекта"""
        
        # Проверяем наличие book.pdf
        if not Path("book.pdf").exists():
            print(f"{Colors.RED}❌ Файл book.pdf не найден!{Colors.RESET}")
            return False
        
        # Получаем информацию о книге
        book_info = self.get_book_info()
        
        # Генерируем имя проекта если не указано
        if not project_name:
            book_title = book_info["title"] or "book"
            # Очищаем от недопустимых символов
            book_title = "".join(c for c in book_title if c.isalnum() or c in " -_")[:50]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = f"{book_title}_{timestamp}"
        
        # Проверяем что проект не существует
        project_path = self.projects_dir / f"{project_name}.tar.gz"
        if project_path.exists():
            print(f"{Colors.YELLOW}⚠️  Проект '{project_name}' уже существует!{Colors.RESET}")
            response = input("Перезаписать? (y/n): ")
            if response.lower() != 'y':
                return False
        
        print(f"{Colors.CYAN}📦 Архивирование проекта '{project_name}'...{Colors.RESET}")
        
        # Собираем статистику
        stats = self.collect_stats()
        
        # Создаем архив
        with tarfile.open(project_path, "w:gz") as tar:
            # Архивируем директории
            for dir_name in self.work_dirs:
                if Path(dir_name).exists():
                    print(f"  📁 {dir_name}/")
                    tar.add(dir_name)
            
            # Архивируем файлы
            for file_name in self.work_files:
                if Path(file_name).exists():
                    print(f"  📄 {file_name}")
                    tar.add(file_name)
        
        # Сохраняем метаданные
        self.projects[project_name] = {
            "created": datetime.now().isoformat(),
            "description": description,
            "book": book_info,
            "stats": stats,
            "archive": str(project_path.name)
        }
        self.save_metadata()
        
        # Вычисляем размер архива
        archive_size = project_path.stat().st_size / (1024 * 1024)  # MB
        
        print(f"{Colors.GREEN}✅ Проект архивирован: {project_path}{Colors.RESET}")
        print(f"   Размер архива: {archive_size:.1f} MB")
        print(f"   Глав переведено: {stats['translated_chapters']}/{stats['total_chapters']}")
        
        return True
    
    def restore_project(self, project_name):
        """Восстановление проекта из архива"""
        
        if project_name not in self.projects:
            print(f"{Colors.RED}❌ Проект '{project_name}' не найден!{Colors.RESET}")
            self.list_projects()
            return False
        
        project_info = self.projects[project_name]
        archive_path = self.projects_dir / project_info["archive"]
        
        if not archive_path.exists():
            print(f"{Colors.RED}❌ Архив {archive_path} не найден!{Colors.RESET}")
            return False
        
        # Проверяем текущее состояние
        if self.check_workspace_dirty():
            print(f"{Colors.YELLOW}⚠️  В рабочей директории есть несохраненные изменения!{Colors.RESET}")
            response = input("Продолжить? Все текущие данные будут потеряны (y/n): ")
            if response.lower() != 'y':
                return False
        
        print(f"{Colors.CYAN}📂 Восстановление проекта '{project_name}'...{Colors.RESET}")
        
        # Очищаем рабочее пространство
        self.clean_workspace()
        
        # Распаковываем архив
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall()
        
        # Сохраняем информацию о текущем проекте
        with open(self.current_file, 'w') as f:
            f.write(project_name)
        
        print(f"{Colors.GREEN}✅ Проект восстановлен!{Colors.RESET}")
        self.show_project_info(project_name)
        
        return True
    
    def clean_workspace(self):
        """Очистка рабочего пространства"""
        print(f"{Colors.YELLOW}🧹 Очистка рабочего пространства...{Colors.RESET}")
        
        for dir_name in self.work_dirs:
            if Path(dir_name).exists():
                shutil.rmtree(dir_name)
                print(f"  ❌ Удалено: {dir_name}/")
        
        # Удаляем book.pdf только если это не символическая ссылка
        if Path("book.pdf").exists() and not Path("book.pdf").is_symlink():
            Path("book.pdf").unlink()
            print(f"  ❌ Удалено: book.pdf")
    
    def check_workspace_dirty(self):
        """Проверка наличия несохраненных данных"""
        for dir_name in self.work_dirs:
            if Path(dir_name).exists() and any(Path(dir_name).iterdir()):
                return True
        
        if Path("book.pdf").exists():
            return True
        
        return False
    
    def collect_stats(self):
        """Сбор статистики о проекте"""
        stats = {
            "total_chapters": 0,
            "translated_chapters": 0,
            "figures_extracted": 0,
            "output_files": 0,
            "audio_files": 0,
            "adapted_chapters": 0,
            "adapted_audio_files": 0,
            "total_size_mb": 0
        }
        
        # Считаем главы
        extracted_dir = Path("extracted_fixed")
        if not extracted_dir.exists():
            extracted_dir = Path("extracted")
        
        if extracted_dir.exists():
            chapters = list(extracted_dir.glob("chapter_*.json"))
            stats["total_chapters"] = len(chapters)
        
        # Считаем переводы
        trans_dir = Path("translations")
        if trans_dir.exists():
            translations = list(trans_dir.glob("chapter_*_translated.json"))
            stats["translated_chapters"] = len(translations)
        
        # Считаем диаграммы
        figures_dir = Path("figures")
        if figures_dir.exists():
            figures = list(figures_dir.glob("*.png"))
            stats["figures_extracted"] = len(figures)
        
        # Считаем выходные файлы
        output_dir = Path("output")
        if output_dir.exists():
            outputs = list(output_dir.glob("*.pdf")) + list(output_dir.glob("*.epub"))
            stats["output_files"] = len(outputs)
        
        # Считаем аудио файлы v1.0
        audiobook_dir = Path("audiobook")
        if audiobook_dir.exists():
            audio_files = list(audiobook_dir.glob("*.mp3"))
            stats["audio_files"] = len(audio_files)
        
        # Считаем адаптированные главы
        adapted_dir = Path("audio_adapted")
        if adapted_dir.exists():
            adapted = list(adapted_dir.glob("chapter_*_translated_audio.json"))
            stats["adapted_chapters"] = len(adapted)
        
        # Считаем адаптированные аудио файлы v2.0
        adapted_audio_dir = Path("audiobook_adapted")
        if adapted_audio_dir.exists():
            adapted_audio = list(adapted_audio_dir.glob("*.mp3"))
            stats["adapted_audio_files"] = len(adapted_audio)
        
        # Считаем общий размер
        total_size = 0
        for dir_name in self.work_dirs:
            if Path(dir_name).exists():
                for file_path in Path(dir_name).rglob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
        
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 1)
        
        return stats
    
    def list_projects(self):
        """Список всех сохраненных проектов"""
        if not self.projects:
            print(f"{Colors.YELLOW}📭 Нет сохраненных проектов{Colors.RESET}")
            return
        
        print(f"{Colors.BOLD}{Colors.CYAN}📚 Сохраненные проекты:{Colors.RESET}")
        print("=" * 80)
        
        for idx, (name, info) in enumerate(self.projects.items(), 1):
            created = datetime.fromisoformat(info["created"]).strftime("%Y-%m-%d %H:%M")
            book_title = info["book"]["title"] or "Без названия"
            pages = info["book"]["pages"]
            translated = info["stats"]["translated_chapters"]
            total = info["stats"]["total_chapters"]
            
            status_color = Colors.GREEN if translated == total and total > 0 else Colors.YELLOW
            status = f"{status_color}{translated}/{total}{Colors.RESET}"
            
            print(f"{idx:2}. {Colors.BOLD}{name}{Colors.RESET}")
            print(f"    📖 {book_title} ({pages} стр.)")
            print(f"    📅 {created} | 📊 Переведено: {status}")
            
            if info.get("description"):
                print(f"    💬 {info['description']}")
            
            print()
    
    def show_project_info(self, project_name):
        """Показать информацию о проекте"""
        if project_name not in self.projects:
            return
        
        info = self.projects[project_name]
        stats = info["stats"]
        book = info["book"]
        
        print(f"\n{Colors.BOLD}📋 Информация о проекте:{Colors.RESET}")
        print(f"  📖 Книга: {book['title']} ({book['pages']} стр.)")
        print(f"  📊 Переведено глав: {stats['translated_chapters']}/{stats['total_chapters']}")
        print(f"  🖼️  Извлечено диаграмм: {stats['figures_extracted']}")
        print(f"  📄 Выходных файлов: {stats['output_files']}")
        
        # Добавляем информацию об аудио v1.0
        if stats.get('audio_files', 0) > 0:
            print(f"  🎵 Аудио файлов: {stats['audio_files']}")
        
        # Добавляем информацию об адаптации v2.0
        if stats.get('adapted_chapters', 0) > 0:
            print(f"  📝 Адаптировано для аудио: {stats['adapted_chapters']} глав")
        
        if stats.get('adapted_audio_files', 0) > 0:
            print(f"  🎙️  Адаптированных аудио: {stats['adapted_audio_files']}")
        
        print(f"  💾 Размер данных: {stats['total_size_mb']} MB")
    
    def switch_project(self, project_name):
        """Переключение на другой проект"""
        # Сначала сохраняем текущий если есть изменения
        if self.check_workspace_dirty():
            print(f"{Colors.YELLOW}⚠️  Обнаружены несохраненные изменения{Colors.RESET}")
            response = input("Сохранить текущий проект? (y/n): ")
            if response.lower() == 'y':
                current_name = input("Имя для сохранения (Enter для автоматического): ").strip()
                self.archive_project(current_name or None)
        
        # Восстанавливаем выбранный проект
        return self.restore_project(project_name)
    
    def get_current_project(self):
        """Получить имя текущего проекта"""
        if self.current_file.exists():
            with open(self.current_file, 'r') as f:
                return f.read().strip()
        return None


def main():
    """Интерфейс командной строки"""
    manager = ProjectManager()
    
    if len(sys.argv) < 2:
        print(f"{Colors.BOLD}🗂️  Менеджер проектов переводчика книг{Colors.RESET}")
        print()
        print("Использование:")
        print("  python project_manager.py save [name] [description]  - Сохранить текущий проект")
        print("  python project_manager.py load <name>                - Загрузить проект")
        print("  python project_manager.py list                       - Список проектов")
        print("  python project_manager.py switch <name>              - Переключиться на проект")
        print("  python project_manager.py clean                      - Очистить рабочее пространство")
        print("  python project_manager.py current                    - Показать текущий проект")
        return
    
    command = sys.argv[1]
    
    if command == "save":
        name = sys.argv[2] if len(sys.argv) > 2 else None
        description = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        manager.archive_project(name, description)
    
    elif command == "load" or command == "restore":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}❌ Укажите имя проекта{Colors.RESET}")
            manager.list_projects()
        else:
            manager.restore_project(sys.argv[2])
    
    elif command == "list":
        manager.list_projects()
    
    elif command == "switch":
        if len(sys.argv) < 3:
            print(f"{Colors.RED}❌ Укажите имя проекта{Colors.RESET}")
            manager.list_projects()
        else:
            manager.switch_project(sys.argv[2])
    
    elif command == "clean":
        if manager.check_workspace_dirty():
            print(f"{Colors.YELLOW}⚠️  В рабочей директории есть данные!{Colors.RESET}")
            response = input("Точно очистить всё? (yes/no): ")
            if response.lower() == 'yes':
                manager.clean_workspace()
                print(f"{Colors.GREEN}✅ Рабочее пространство очищено{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}✅ Рабочее пространство уже чистое{Colors.RESET}")
    
    elif command == "current":
        current = manager.get_current_project()
        if current:
            print(f"{Colors.CYAN}📍 Текущий проект: {Colors.BOLD}{current}{Colors.RESET}")
            manager.show_project_info(current)
        else:
            print(f"{Colors.YELLOW}📭 Нет активного проекта{Colors.RESET}")
    
    else:
        print(f"{Colors.RED}❌ Неизвестная команда: {command}{Colors.RESET}")


if __name__ == "__main__":
    main()