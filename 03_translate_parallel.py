#!/usr/bin/env python3
"""
Параллельный интерактивный переводчик с многопоточностью и живым интерфейсом
"""

import json
import os
import sys
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import re
from dataclasses import dataclass
from enum import Enum

from deepseek_translator import DeepSeekTranslator
from translation_manager import TranslationProgress, ContextManager

# ANSI коды для управления терминалом
class Terminal:
    CLEAR = '\033[2J'
    HOME = '\033[H'
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'
    SAVE_CURSOR = '\033[s'
    RESTORE_CURSOR = '\033[u'
    
    @staticmethod
    def move_to(row, col):
        return f'\033[{row};{col}H'
    
    @staticmethod
    def clear_line():
        return '\033[K'
    
    @staticmethod
    def clear_below():
        return '\033[J'

# Цвета
class Colors:
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    BG_BLACK = '\033[40m'
    BG_BLUE = '\033[44m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_RED = '\033[41m'

class WorkerStatus(Enum):
    IDLE = "⚪ Ожидание"
    PREPARING = "🔄 Подготовка"
    SENDING = "📤 Отправка"
    WAITING = "⏳ Ожидание API"
    PROCESSING = "⚙️ Обработка"
    COMPLETED = "✅ Завершено"
    ERROR = "❌ Ошибка"

@dataclass
class WorkerState:
    id: int
    status: WorkerStatus
    current_chapter: Optional[int] = None
    current_block: Optional[int] = None
    total_blocks: int = 0
    chars_sent: int = 0
    chars_received: int = 0
    api_time: float = 0
    error_msg: str = ""
    progress: float = 0
    last_update: datetime = None

@dataclass
class TranslationTask:
    chapter_num: int
    chapter_data: Dict
    context: Dict
    block_idx: int
    block_data: Dict
    total_blocks: int

class ParallelTranslator:
    def __init__(self, max_workers=25):
        self.max_workers = max_workers
        self.progress_tracker = TranslationProgress()
        self.context_manager = ContextManager()
        
        # Создаем пул транслаторов для каждого потока
        self.translators = [DeepSeekTranslator() for _ in range(max_workers)]
        
        # Состояние воркеров
        self.workers = {i: WorkerState(id=i, status=WorkerStatus.IDLE) 
                       for i in range(max_workers)}
        
        # Очереди задач
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # Блокировки для синхронизации
        self.screen_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        
        # Глобальная статистика
        self.global_stats = {
            "total_chapters": 0,
            "completed_chapters": 0,
            "total_blocks": 0,
            "completed_blocks": 0,
            "chars_sent": 0,
            "chars_received": 0,
            "api_calls": 0,
            "api_errors": 0,
            "start_time": None,
            "estimated_cost": 0.0,
            "active_workers": 0
        }
        
        # Флаги управления
        self.stop_flag = threading.Event()
        self.pause_flag = threading.Event()
        
        # Размеры терминала
        try:
            self.term_width = os.get_terminal_size().columns
            self.term_height = os.get_terminal_size().lines
        except:
            self.term_width = 80
            self.term_height = 24
        
    def clear_screen(self):
        """Очистка экрана и переход в начало"""
        print(Terminal.CLEAR + Terminal.HOME, end='', flush=True)
        
    def draw_header(self):
        """Отрисовка заголовка"""
        header = f"{'='*self.term_width}"[:self.term_width]
        title = " 🚀 ПАРАЛЛЕЛЬНЫЙ ПЕРЕВОДЧИК DEEPSEEK (25 ПОТОКОВ) "
        padding = (self.term_width - len(title)) // 2
        
        print(Terminal.move_to(1, 1) + Colors.BRIGHT_CYAN + Colors.BOLD + header + Colors.RESET)
        print(Terminal.move_to(2, padding) + Colors.BRIGHT_CYAN + Colors.BOLD + title + Colors.RESET)
        print(Terminal.move_to(3, 1) + Colors.BRIGHT_CYAN + Colors.BOLD + header + Colors.RESET)
        
    def draw_global_stats(self):
        """Отрисовка глобальной статистики"""
        row = 5
        
        if not self.global_stats["start_time"]:
            elapsed = "00:00:00"
            speed = 0
        else:
            elapsed_delta = datetime.now() - self.global_stats["start_time"]
            elapsed = str(elapsed_delta).split('.')[0]
            speed = self.global_stats["chars_sent"] / max(1, elapsed_delta.total_seconds())
        
        # Прогресс
        progress_pct = self.global_stats["completed_blocks"] / max(1, self.global_stats["total_blocks"]) * 100
        progress_bar_width = 40
        filled = int(progress_bar_width * progress_pct / 100)
        progress_bar = '█' * filled + '░' * (progress_bar_width - filled)
        
        stats_text = [
            f"{Colors.BOLD}📊 ОБЩАЯ СТАТИСТИКА{Colors.RESET}",
            "",
            f"Прогресс: {Colors.GREEN}|{progress_bar}|{Colors.RESET} {progress_pct:.1f}%",
            f"Главы: {Colors.BRIGHT_YELLOW}{self.global_stats['completed_chapters']}/{self.global_stats['total_chapters']}{Colors.RESET} • "
            f"Блоки: {Colors.BRIGHT_YELLOW}{self.global_stats['completed_blocks']}/{self.global_stats['total_blocks']}{Colors.RESET}",
            f"Время: {Colors.BRIGHT_CYAN}{elapsed}{Colors.RESET} • "
            f"Скорость: {Colors.BRIGHT_CYAN}{speed:.0f}{Colors.RESET} симв/сек",
            f"API: {Colors.BRIGHT_GREEN}{self.global_stats['api_calls']}{Colors.RESET} запросов • "
            f"Ошибки: {Colors.BRIGHT_RED}{self.global_stats['api_errors']}{Colors.RESET}",
            f"Отправлено: {Colors.BRIGHT_BLUE}{self.global_stats['chars_sent']:,}{Colors.RESET} • "
            f"Получено: {Colors.BRIGHT_BLUE}{self.global_stats['chars_received']:,}{Colors.RESET}",
            f"Стоимость: {Colors.BRIGHT_MAGENTA}${self.global_stats['estimated_cost']:.4f}{Colors.RESET} • "
            f"Активно: {Colors.BRIGHT_GREEN}{self.global_stats['active_workers']}/{self.max_workers}{Colors.RESET} потоков"
        ]
        
        for i, line in enumerate(stats_text):
            print(Terminal.move_to(row + i, 3) + Terminal.clear_line() + line)
        
    def draw_worker_status(self):
        """Отрисовка статуса воркеров"""
        start_row = 15
        
        # Адаптивная компоновка для разного количества воркеров
        if self.max_workers <= 10:
            cols = 2
            rows_per_col = 5
        elif self.max_workers <= 15:
            cols = 3
            rows_per_col = 5
        elif self.max_workers <= 20:
            cols = 4
            rows_per_col = 5
        else:  # 21-30 воркеров
            cols = 5
            rows_per_col = 6
        
        cols_width = self.term_width // cols
        
        print(Terminal.move_to(start_row - 1, 3) + Colors.BOLD + f"🔧 СОСТОЯНИЕ ПОТОКОВ ({self.max_workers}):" + Colors.RESET)
        
        for worker_id, state in self.workers.items():
            col_idx = worker_id // rows_per_col
            row_idx = worker_id % rows_per_col
            
            row = start_row + row_idx * 2
            col = 3 + col_idx * cols_width
            
            # Цвет в зависимости от статуса
            if state.status == WorkerStatus.IDLE:
                color = Colors.BRIGHT_BLACK
            elif state.status == WorkerStatus.ERROR:
                color = Colors.BRIGHT_RED
            elif state.status == WorkerStatus.COMPLETED:
                color = Colors.BRIGHT_GREEN
            elif state.status in [WorkerStatus.SENDING, WorkerStatus.WAITING]:
                color = Colors.BRIGHT_YELLOW
            else:
                color = Colors.BRIGHT_CYAN
            
            # Прогресс воркера
            if state.total_blocks > 0:
                progress = f"{state.current_block}/{state.total_blocks}"
            else:
                progress = "-/-"
            
            # Информация о воркере
            if state.current_chapter is not None:
                chapter_info = f"Гл.{state.current_chapter:03d}"
            else:
                chapter_info = "---"
            
            # Компактный вывод для большого количества воркеров
            if self.max_workers > 15:
                status_line = f"{color}[{worker_id:02d}]{state.status.value[:8]:<8} {chapter_info}{Colors.RESET}"
            else:
                status_line = f"{color}[{worker_id:02d}] {state.status.value:<15} {chapter_info} {progress:>7}{Colors.RESET}"
            
            # Дополнительная информация
            if state.api_time > 0:
                extra = f" {Colors.DIM}({state.api_time:.1f}с){Colors.RESET}"
            elif state.error_msg:
                extra = f" {Colors.RED}{state.error_msg[:20]}{Colors.RESET}"
            else:
                extra = ""
            
            print(Terminal.move_to(row, col) + Terminal.clear_line() + status_line + extra)
            
            # Прогресс-бар для активных воркеров
            if state.status not in [WorkerStatus.IDLE, WorkerStatus.ERROR]:
                bar_width = 20
                filled = int(bar_width * state.progress / 100)
                bar = '▰' * filled + '▱' * (bar_width - filled)
                print(Terminal.move_to(row + 1, col + 5) + Colors.DIM + bar + Colors.RESET)
    
    def draw_log(self, messages: List[str]):
        """Отрисовка лога"""
        start_row = 26
        max_messages = self.term_height - start_row - 2
        
        print(Terminal.move_to(start_row, 3) + Colors.BOLD + "📜 ПОСЛЕДНИЕ СОБЫТИЯ:" + Colors.RESET)
        
        for i, msg in enumerate(messages[-max_messages:]):
            print(Terminal.move_to(start_row + 1 + i, 3) + Terminal.clear_line() + Colors.DIM + msg[:self.term_width-6] + Colors.RESET)
    
    def draw_footer(self):
        """Отрисовка подвала"""
        footer_row = self.term_height - 1
        footer = f" [Ctrl+C] Пауза • [Ctrl+D] Остановка • Очередь: {self.task_queue.qsize()} "
        padding = (self.term_width - len(footer)) // 2
        
        print(Terminal.move_to(footer_row, padding) + Colors.BG_BLUE + Colors.WHITE + footer + Colors.RESET, end='', flush=True)
    
    def update_screen(self, log_messages):
        """Обновление всего экрана"""
        with self.screen_lock:
            self.draw_header()
            self.draw_global_stats()
            self.draw_worker_status()
            self.draw_log(log_messages)
            self.draw_footer()
    
    def worker_thread(self, worker_id: int):
        """Рабочий поток для перевода"""
        translator = self.translators[worker_id]
        log_messages = []
        
        while not self.stop_flag.is_set():
            try:
                # Получаем задачу из очереди
                task = self.task_queue.get(timeout=1)
                
                if task is None:  # Сигнал остановки
                    break
                
                # Обновляем статус
                self.workers[worker_id].status = WorkerStatus.PREPARING
                self.workers[worker_id].current_chapter = task.chapter_num
                self.workers[worker_id].current_block = task.block_idx
                self.workers[worker_id].total_blocks = task.total_blocks
                self.workers[worker_id].progress = 0
                
                with self.stats_lock:
                    self.global_stats["active_workers"] += 1
                
                # Подготовка данных
                paragraph_group = task.block_data
                
                # Пропускаем если нет текста
                if not paragraph_group["text"].strip():
                    result = {"paragraphs": paragraph_group["paragraphs"], "skipped": True}
                else:
                    # Извлекаем текст для перевода
                    text_paragraphs = [p for p in paragraph_group["paragraphs"] if not p.startswith("[IMAGE_")]
                    text_to_translate = "\n\n".join(text_paragraphs)
                    
                    # Обновляем статус
                    self.workers[worker_id].status = WorkerStatus.SENDING
                    self.workers[worker_id].chars_sent = len(text_to_translate)
                    
                    # Отправляем запрос
                    start_time = time.time()
                    try:
                        # Подготовка промптов
                        system_prompt = translator._create_system_prompt(task.context)
                        text_with_placeholders = translator._preserve_placeholders(text_to_translate)
                        
                        self.workers[worker_id].status = WorkerStatus.WAITING
                        
                        # API запрос
                        response = translator.client.chat.completions.create(
                            model="deepseek-chat",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"""Переведи следующий текст на русский язык. 
Требования:
1. Сохрани все плейсхолдеры [IMAGE_XXX] без изменений
2. Используй профессиональную терминологию для IT и управления проектами
3. Сохрани структуру абзацев (разделение через \\n\\n)
4. Адаптируй под российскую IT-индустрию

Текст для перевода:
{text_with_placeholders}"""}
                            ],
                            temperature=0.3,
                            max_tokens=3000
                        )
                        
                        api_time = time.time() - start_time
                        
                        # Обработка ответа
                        self.workers[worker_id].status = WorkerStatus.PROCESSING
                        self.workers[worker_id].api_time = api_time
                        
                        translated = response.choices[0].message.content
                        translated = translator._restore_placeholders(translated)
                        
                        # Статистика
                        self.workers[worker_id].chars_received = len(translated)
                        
                        with self.stats_lock:
                            self.global_stats["api_calls"] += 1
                            self.global_stats["chars_sent"] += len(text_to_translate)
                            self.global_stats["chars_received"] += len(translated)
                            
                            # Оценка стоимости
                            input_tokens = len(text_to_translate) / 4
                            output_tokens = len(translated) / 4
                            cost = (input_tokens * 0.14 + output_tokens * 0.28) / 1_000_000
                            self.global_stats["estimated_cost"] += cost
                        
                        # Восстановление структуры с изображениями
                        translated_parts = translated.split('\n\n')
                        result_paragraphs = []
                        text_idx = 0
                        
                        for original in paragraph_group["paragraphs"]:
                            if original.startswith("[IMAGE_"):
                                result_paragraphs.append(original)
                            else:
                                if text_idx < len(translated_parts):
                                    result_paragraphs.append(translated_parts[text_idx])
                                    text_idx += 1
                                else:
                                    result_paragraphs.append(translator._fallback_translate(original))
                        
                        result = {"paragraphs": result_paragraphs, "success": True}
                        
                        # Лог
                        log_msg = f"[{worker_id:02d}] Гл.{task.chapter_num} Бл.{task.block_idx}/{task.total_blocks} - {api_time:.1f}с"
                        log_messages.append(f"{datetime.now().strftime('%H:%M:%S')} {log_msg}")
                        
                    except Exception as e:
                        self.workers[worker_id].status = WorkerStatus.ERROR
                        self.workers[worker_id].error_msg = str(e)[:30]
                        
                        with self.stats_lock:
                            self.global_stats["api_errors"] += 1
                        
                        # Запасной перевод
                        result_paragraphs = []
                        for p in paragraph_group["paragraphs"]:
                            if p.startswith("[IMAGE_"):
                                result_paragraphs.append(p)
                            else:
                                result_paragraphs.append(translator._fallback_translate(p))
                        
                        result = {"paragraphs": result_paragraphs, "error": str(e)}
                        
                        log_msg = f"[{worker_id:02d}] Ошибка: {str(e)[:50]}"
                        log_messages.append(f"{datetime.now().strftime('%H:%M:%S')} {log_msg}")
                
                # Отправляем результат
                self.result_queue.put((task, result))
                
                # Обновляем статус
                self.workers[worker_id].status = WorkerStatus.COMPLETED
                self.workers[worker_id].progress = 100
                
                with self.stats_lock:
                    self.global_stats["completed_blocks"] += 1
                    self.global_stats["active_workers"] -= 1
                
                # Небольшая задержка
                time.sleep(0.1)
                
                # Сбрасываем статус
                self.workers[worker_id].status = WorkerStatus.IDLE
                self.workers[worker_id].current_chapter = None
                self.workers[worker_id].current_block = None
                
            except queue.Empty:
                continue
            except Exception as e:
                log_messages.append(f"[{worker_id:02d}] Критическая ошибка: {e}")
    
    def screen_updater_thread(self, log_messages):
        """Поток для обновления экрана"""
        while not self.stop_flag.is_set():
            self.update_screen(log_messages)
            time.sleep(0.1)  # Обновление 10 раз в секунду
    
    def translate_chapters(self, chapters: List[Dict]):
        """Основной метод параллельного перевода"""
        # Инициализация
        self.global_stats["total_chapters"] = len(chapters)
        self.global_stats["start_time"] = datetime.now()
        log_messages = []
        
        # Подготовка задач
        all_tasks = []
        
        for chapter_info in chapters:
            chapter_num = chapter_info['number']
            
            # Пропускаем переведенные
            if self.progress_tracker.is_chapter_translated(chapter_num):
                self.global_stats["completed_chapters"] += 1
                log_messages.append(f"Глава {chapter_num} уже переведена")
                continue
            
            # Загружаем главу
            chapter_file = Path(f"extracted_fixed/chapter_{chapter_num:03d}.json")
            if not chapter_file.exists():
                log_messages.append(f"Файл главы {chapter_num} не найден")
                continue
            
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter_data = json.load(f)
            
            # Создаем контекст
            context = self.context_manager.create_context_for_chapter(chapter_num)
            
            # Группируем параграфы
            translator = DeepSeekTranslator()
            paragraph_groups = translator._group_paragraphs(chapter_data["paragraphs"], max_chars=800)
            
            # Создаем задачи для каждого блока
            for block_idx, block_data in enumerate(paragraph_groups):
                task = TranslationTask(
                    chapter_num=chapter_num,
                    chapter_data=chapter_data,
                    context=context,
                    block_idx=block_idx,
                    block_data=block_data,
                    total_blocks=len(paragraph_groups)
                )
                all_tasks.append(task)
        
        self.global_stats["total_blocks"] = len(all_tasks)
        
        # Скрываем курсор
        print(Terminal.HIDE_CURSOR, end='', flush=True)
        
        try:
            # Очищаем экран
            self.clear_screen()
            
            # Запускаем поток обновления экрана
            screen_thread = threading.Thread(target=self.screen_updater_thread, args=(log_messages,))
            screen_thread.daemon = True
            screen_thread.start()
            
            # Создаем пул воркеров
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Запускаем воркеры
                workers = []
                for i in range(self.max_workers):
                    worker = executor.submit(self.worker_thread, i)
                    workers.append(worker)
                
                # Добавляем задачи в очередь
                for task in all_tasks:
                    self.task_queue.put(task)
                
                # Обрабатываем результаты
                results_by_chapter = {}
                processed = 0
                
                while processed < len(all_tasks):
                    try:
                        task, result = self.result_queue.get(timeout=1)
                        
                        # Сохраняем результат
                        chapter_num = task.chapter_num
                        if chapter_num not in results_by_chapter:
                            results_by_chapter[chapter_num] = {
                                "chapter_data": task.chapter_data,
                                "blocks": {},
                                "total_blocks": task.total_blocks
                            }
                        
                        results_by_chapter[chapter_num]["blocks"][task.block_idx] = result
                        
                        # Проверяем, собрали ли всю главу
                        if len(results_by_chapter[chapter_num]["blocks"]) == task.total_blocks:
                            # Собираем главу
                            self._save_chapter(chapter_num, results_by_chapter[chapter_num])
                            self.global_stats["completed_chapters"] += 1
                            log_messages.append(f"✅ Глава {chapter_num} переведена и сохранена")
                            
                            # Освобождаем память
                            del results_by_chapter[chapter_num]
                        
                        processed += 1
                        
                    except queue.Empty:
                        continue
                    except KeyboardInterrupt:
                        log_messages.append("⏸️  Получен сигнал остановки...")
                        self.stop_flag.set()
                        break
                
                # Останавливаем воркеры
                for _ in range(self.max_workers):
                    self.task_queue.put(None)
                
                # Ждем завершения
                for worker in workers:
                    worker.result(timeout=5)
        
        finally:
            # Показываем курсор
            print(Terminal.SHOW_CURSOR, end='', flush=True)
            self.stop_flag.set()
            
            # Финальный экран
            self.clear_screen()
            self._show_final_stats()
    
    def _save_chapter(self, chapter_num: int, chapter_results: Dict):
        """Сохранение переведенной главы"""
        # Собираем все параграфы в правильном порядке
        all_paragraphs = []
        for i in range(chapter_results["total_blocks"]):
            if i in chapter_results["blocks"]:
                all_paragraphs.extend(chapter_results["blocks"][i]["paragraphs"])
        
        # Создаем результат перевода
        translator = DeepSeekTranslator()
        chapter_data = chapter_results["chapter_data"]
        
        translation = {
            "number": chapter_num,
            "title": translator._translate_title(chapter_data["title"]),
            "paragraphs": all_paragraphs,
            "summary": translator._generate_summary(all_paragraphs),
            "original_word_count": chapter_data["word_count"],
            "translator": "DeepSeek Parallel"
        }
        
        # Сохраняем
        translator.save_translation(chapter_num, translation)
        self.progress_tracker.mark_chapter_complete(chapter_num)
    
    def _show_final_stats(self):
        """Показ финальной статистики"""
        if not self.global_stats["start_time"]:
            return
        
        elapsed = datetime.now() - self.global_stats["start_time"]
        
        print(Colors.BOLD + Colors.BRIGHT_CYAN + "="*80 + Colors.RESET)
        print(Colors.BOLD + Colors.BRIGHT_CYAN + " ПЕРЕВОД ЗАВЕРШЕН ".center(80, "=") + Colors.RESET)
        print(Colors.BOLD + Colors.BRIGHT_CYAN + "="*80 + Colors.RESET)
        print()
        
        stats = [
            ("✅ Переведено глав", f"{self.global_stats['completed_chapters']}/{self.global_stats['total_chapters']}"),
            ("📦 Обработано блоков", f"{self.global_stats['completed_blocks']}/{self.global_stats['total_blocks']}"),
            ("⏱️  Общее время", str(elapsed).split('.')[0]),
            ("🚀 Использовано потоков", str(self.max_workers)),
            ("📤 Отправлено", f"{self.global_stats['chars_sent']:,} символов"),
            ("📥 Получено", f"{self.global_stats['chars_received']:,} символов"),
            ("🌐 API запросов", str(self.global_stats['api_calls'])),
            ("❌ Ошибок", str(self.global_stats['api_errors'])),
            ("💰 Стоимость", f"${self.global_stats['estimated_cost']:.2f}"),
        ]
        
        if self.global_stats['api_calls'] > 0:
            avg_time = elapsed.total_seconds() / self.global_stats['api_calls']
            stats.append(("⚡ Среднее время/запрос", f"{avg_time:.1f} сек"))
            
            # Ускорение от параллелизма
            sequential_time = avg_time * self.global_stats['api_calls']
            speedup = sequential_time / elapsed.total_seconds()
            stats.append(("🏎️  Ускорение", f"{speedup:.1f}x"))
        
        for label, value in stats:
            print(f"  {label}: {Colors.BRIGHT_GREEN}{value}{Colors.RESET}")
        
        print()
        print(Colors.BRIGHT_YELLOW + "💡 Используйте 'python main.py compile' для создания книги" + Colors.RESET)


def main():
    """Точка входа"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Параллельный переводчик с 25 потоками')
    parser.add_argument('chapters', nargs='*', type=int, help='Номера глав для перевода')
    parser.add_argument('--workers', '-w', type=int, default=25, help='Количество потоков (по умолчанию 25)')
    parser.add_argument('--all', '-a', action='store_true', help='Перевести все главы')
    
    args = parser.parse_args()
    
    # Загрузка метаданных
    metadata_file = Path("extracted_fixed/metadata.json")
    if not metadata_file.exists():
        print(Colors.RED + "❌ Сначала извлеките содержимое: python main.py extract" + Colors.RESET)
        return
    
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    # Определяем главы
    all_chapters = metadata['chapters']
    progress_tracker = TranslationProgress()
    
    if args.chapters:
        chapters = [c for c in all_chapters if c['number'] in args.chapters]
        print(f"{Colors.CYAN}📋 Выбранные главы: {args.chapters}{Colors.RESET}")
    elif args.all:
        chapters = all_chapters
        print(f"{Colors.CYAN}📋 Перевод всех глав{Colors.RESET}")
    else:
        chapters = [c for c in all_chapters 
                   if not progress_tracker.is_chapter_translated(c['number'])]
        print(f"{Colors.CYAN}📋 Продолжение перевода непереведенных глав{Colors.RESET}")
    
    if not chapters:
        print(f"{Colors.GREEN}✅ Все главы уже переведены!{Colors.RESET}")
        return
    
    print(f"{Colors.BOLD}📚 Всего глав для перевода: {len(chapters)}{Colors.RESET}")
    print(f"{Colors.BOLD}🚀 Запуск {args.workers} параллельных потоков{Colors.RESET}")
    print(f"{Colors.DIM}Нажмите Enter для начала...{Colors.RESET}")
    input()
    
    # Запуск параллельного перевода
    translator = ParallelTranslator(max_workers=args.workers)
    translator.translate_chapters(chapters)


if __name__ == "__main__":
    main()