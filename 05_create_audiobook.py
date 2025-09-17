#!/usr/bin/env python3
"""
Генератор аудиокниги из переведенного текста с использованием edge-tts
Параллельная генерация до 25 потоков для ускорения процесса
"""

import json
import os
import sys
import time
import asyncio
import argparse
import resource
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import subprocess
from typing import List, Tuple, Optional
import hashlib
import re

# Для красивого прогресса
from tqdm import tqdm

# Пробуем импортировать edge-tts
try:
    import edge_tts
except ImportError:
    print("❌ edge-tts не установлен. Установите: pip install edge-tts")
    sys.exit(1)

# Пробуем импортировать pydub для работы с аудио
try:
    from pydub import AudioSegment
    # Проверяем, что pydub действительно работает
    AudioSegment.empty()
    PYDUB_AVAILABLE = True
except (ImportError, Exception):
    # pydub может быть несовместим с Python 3.13+
    AudioSegment = None
    PYDUB_AVAILABLE = False


class AudioBookGenerator:
    def __init__(self, translations_dir="translations", output_dir="audiobook", workers=25, paragraphs_per_group=3, enable_phonetic=True):
        self.translations_dir = Path(translations_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Директория для временных аудиофайлов
        self.temp_dir = self.output_dir / "temp_audio"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Определяем безопасное количество воркеров
        self.workers = self._get_safe_worker_count(workers)
        self.paragraphs_per_group = paragraphs_per_group  # Размер группы параграфов
        self.enable_phonetic = enable_phonetic  # Включить фонетическую замену
        
        # Голос для озвучки (русские голоса edge-tts)
        self.voices = {
            'male': 'ru-RU-DmitryNeural',      # Мужской голос
            'female': 'ru-RU-SvetlanaNeural'   # Женский голос
        }
        self.selected_voice = self.voices['male']  # По умолчанию мужской
        
        # Настройки речи
        self.rate = "+0%"  # Скорость речи (можно менять: -50% до +100%)
        self.volume = "+0%"  # Громкость (можно менять: -50% до +100%)
        
        self.metadata = {
            "chapters": [],
            "total_duration": 0,
            "voice": self.selected_voice,
            "generation_date": datetime.now().isoformat()
        }
        
        # Флаг для отладки фонетической замены
        self._first_phonetic = True
        
        # Словарь фонетических замен для английских терминов
        if self.enable_phonetic:
            self._init_phonetic_replacements()
    
    def _init_phonetic_replacements(self):
        """Инициализация словаря фонетических замен"""
        self.phonetic_replacements = {
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
        
        # Добавляем варианты с точками для аббревиатур
        abbreviations = ['CMMI', 'SEI', 'CAR', 'CM', 'DAR', 'IPM', 'MA', 
                        'OPD', 'OPF', 'OPM', 'OPP', 'OT', 'PI', 'PMC', 
                        'PP', 'PPQA', 'QPM', 'RD', 'REQM', 'RSKM', 'SAM']
        
        for abbr in abbreviations:
            dotted = '.'.join(abbr) + '.'  # C.M.M.I.
            if dotted not in self.phonetic_replacements:
                self.phonetic_replacements[dotted] = self.phonetic_replacements[abbr]
    
    def _get_safe_worker_count(self, requested_workers):
        """Определяет безопасное количество воркеров на основе системных лимитов"""
        try:
            # Получаем лимит открытых файлов
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            
            # Оставляем запас для системы (50% от лимита)
            safe_limit = soft_limit // 2
            
            # Каждый воркер может открывать несколько файлов (примерно 10)
            max_workers = safe_limit // 10
            
            # Выбираем минимум из запрошенного и безопасного
            actual_workers = min(requested_workers, max_workers)
            
            if actual_workers < requested_workers:
                print(f"⚠️ Уменьшаем количество воркеров с {requested_workers} до {actual_workers}")
                print(f"   (системный лимит файлов: {soft_limit})")
                print(f"   Для увеличения выполните: ulimit -n 4096")
            
            return max(1, actual_workers)  # Минимум 1 воркер
            
        except Exception:
            # Если не можем определить лимиты, используем консервативное значение
            return min(requested_workers, 10)
    
    def get_available_voices(self):
        """Получить список доступных русских голосов"""
        print("🎤 Доступные русские голоса:")
        voices = [
            ("ru-RU-DmitryNeural", "Дмитрий (мужской)"),
            ("ru-RU-SvetlanaNeural", "Светлана (женский)"),
            ("ru-RU-DariyaNeural", "Дарья (женский)")
        ]
        for voice_id, name in voices:
            print(f"  • {voice_id}: {name}")
        return voices
    
    def load_translations(self):
        """Загрузка всех переведенных глав"""
        chapters = []
        
        # Ищем все файлы переводов
        translation_files = sorted(self.translations_dir.glob("chapter_*_translated.json"))
        
        if not translation_files:
            print(f"❌ Не найдено переведенных глав в {self.translations_dir}")
            return chapters
        
        print(f"📚 Найдено {len(translation_files)} переведенных глав")
        
        for file_path in translation_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    chapter_data = json.load(f)
                    chapters.append(chapter_data)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки {file_path}: {e}")
        
        return chapters
    
    def apply_phonetic_replacements(self, text):
        """Применяет фонетические замены для английских терминов"""
        if not self.enable_phonetic:
            return text
            
        result = text
        replacements_made = []
        
        # Сортируем по длине (сначала длинные фразы)
        sorted_terms = sorted(self.phonetic_replacements.items(), 
                            key=lambda x: len(x[0]), 
                            reverse=True)
        
        for term, phonetic in sorted_terms:
            # Используем границы слов для точного совпадения
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, result, flags=re.IGNORECASE):
                result = re.sub(pattern, phonetic, result, flags=re.IGNORECASE)
                replacements_made.append(term)
        
        # Показываем информацию о заменах только один раз
        if replacements_made and self._first_phonetic:
            self._first_phonetic = False
            print(f"\n🔤 Фонетическая замена активна! Заменено терминов: {len(replacements_made)}")
            print(f"   Примеры: {', '.join(replacements_made[:5])}")
            print(f"   Эти термины будут произноситься по-русски")
        
        return result
    
    def prepare_text_for_speech(self, text):
        """Подготовка текста для озвучки с фонетической заменой"""
        # Убираем плейсхолдеры изображений
        text = re.sub(r'\[IMAGE_[^\]]+\]', '', text)
        
        # Убираем множественные пробелы
        text = re.sub(r'\s+', ' ', text)
        
        # Применяем фонетические замены для правильного произношения
        text = self.apply_phonetic_replacements(text)
        
        # Добавляем паузы после предложений
        text = re.sub(r'([.!?])\s+', r'\1\n', text)
        
        # Убираем лишние символы
        text = text.strip()
        
        return text
    
    async def generate_audio_chunk(self, text, output_file, chunk_id=None):
        """Асинхронная генерация одного аудио фрагмента"""
        try:
            # Подготавливаем текст с фонетической заменой
            prepared_text = self.prepare_text_for_speech(text)
            
            if not prepared_text:
                return None
            
            # Создаем объект для синтеза
            communicate = edge_tts.Communicate(
                prepared_text,
                self.selected_voice,
                rate=self.rate,
                volume=self.volume
            )
            
            # Генерируем аудио
            await communicate.save(str(output_file))
            
            return output_file
            
        except Exception as e:
            print(f"❌ Ошибка генерации аудио {chunk_id}: {e}")
            return None
    
    def generate_chapter_audio_sync(self, chapter_data, chapter_num):
        """Синхронная обертка для генерации аудио главы"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.generate_chapter_audio(chapter_data, chapter_num)
            )
        finally:
            loop.close()
    
    async def generate_chapter_audio(self, chapter_data, chapter_num):
        """Генерация аудио для одной главы"""
        chapter_audio_files = []
        
        # Создаем вступление главы
        chapter_title = chapter_data.get('title', f'Глава {chapter_num}')
        intro_text = f"Глава {chapter_num}. {chapter_title}."
        
        # Генерируем аудио вступления
        intro_file = self.temp_dir / f"chapter_{chapter_num:03d}_intro.mp3"
        await self.generate_audio_chunk(intro_text, intro_file, f"ch{chapter_num}_intro")
        if intro_file.exists():
            chapter_audio_files.append(intro_file)
        
        # Генерируем аудио для каждого параграфа
        paragraphs = chapter_data.get('paragraphs', [])
        
        for para_idx, paragraph in enumerate(paragraphs):
            # Пропускаем пустые параграфы и изображения
            if not paragraph or paragraph.startswith('[IMAGE_'):
                continue
            
            # Генерируем уникальное имя файла
            para_file = self.temp_dir / f"chapter_{chapter_num:03d}_para_{para_idx:04d}.mp3"
            
            # Генерируем аудио
            result = await self.generate_audio_chunk(
                paragraph, 
                para_file, 
                f"ch{chapter_num}_p{para_idx}"
            )
            
            if result:
                chapter_audio_files.append(para_file)
        
        return chapter_audio_files
    
    def merge_audio_files(self, audio_files, output_file):
        """Объединение аудиофайлов в один"""
        if not PYDUB_AVAILABLE:
            # Используем ffmpeg напрямую (более надежно)
            return self.merge_with_ffmpeg(audio_files, output_file)
        
        try:
            combined = AudioSegment.empty()
            
            for audio_file in audio_files:
                if audio_file.exists():
                    audio = AudioSegment.from_mp3(str(audio_file))
                    # Добавляем небольшую паузу между фрагментами
                    combined += audio + AudioSegment.silent(duration=300)  # 300ms пауза
            
            # Сохраняем результат
            combined.export(str(output_file), format="mp3")
            return True
            
        except Exception as e:
            print(f"⚠️ Ошибка при склейке через pydub: {e}")
            print("   Пробуем через ffmpeg...")
            return self.merge_with_ffmpeg(audio_files, output_file)
    
    def merge_with_ffmpeg(self, audio_files, output_file):
        """Альтернативная склейка через ffmpeg"""
        try:
            # Создаем файл со списком для ffmpeg
            list_file = self.temp_dir / "concat_list.txt"
            with open(list_file, 'w') as f:
                for audio_file in audio_files:
                    if audio_file.exists():
                        f.write(f"file '{audio_file.absolute()}'\n")
            
            # Запускаем ffmpeg
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(list_file),
                '-c', 'copy',
                str(output_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True
            else:
                print(f"❌ ffmpeg error: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка при склейке через ffmpeg: {e}")
            return False
    
    async def generate_audio_wrapper(self, text, output_file, chunk_id):
        """Обертка для асинхронной генерации с управлением ресурсами"""
        try:
            result = await self.generate_audio_chunk(text, output_file, chunk_id)
            return result
        except Exception as e:
            print(f"❌ Ошибка при генерации {chunk_id}: {e}")
            return None
    
    def generate_single_audio_sync(self, task):
        """Синхронная обертка для генерации одного аудио фрагмента"""
        text, output_file, chunk_id = task
        
        # Создаем новый event loop для этого потока
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.generate_audio_wrapper(text, output_file, chunk_id)
            )
            return result
        except Exception as e:
            print(f"❌ Ошибка в generate_single_audio_sync для {chunk_id}: {e}")
            return None
        finally:
            # Важно: закрываем loop для освобождения ресурсов
            try:
                loop.close()
            except:
                pass
    
    def prepare_generation_tasks(self, chapters):
        """Подготовка задач для параллельной генерации - группами параграфов"""
        tasks = []
        
        for chapter_idx, chapter_data in enumerate(chapters):
            chapter_num = chapter_idx
            chapter_title = chapter_data.get('title', f'Глава {chapter_num}')
            
            # Добавляем задачу для вступления главы
            intro_text = f"Глава {chapter_num}. {chapter_title}."
            intro_file = self.temp_dir / f"chapter_{chapter_num:03d}_intro.mp3"
            tasks.append((intro_text, intro_file, f"ch{chapter_num}_intro"))
            
            # Группируем параграфы по 3 штуки (как при переводе)
            paragraphs = chapter_data.get('paragraphs', [])
            
            # Фильтруем только текстовые параграфы
            text_paragraphs = []
            for para in paragraphs:
                if para and not para.startswith('[IMAGE_'):
                    text_paragraphs.append(para)
            
            # Создаем группы параграфов
            for group_idx in range(0, len(text_paragraphs), self.paragraphs_per_group):
                group_end = min(group_idx + self.paragraphs_per_group, len(text_paragraphs))
                paragraph_group = text_paragraphs[group_idx:group_end]
                
                if paragraph_group:
                    # Объединяем параграфы с паузами между ними
                    group_text = "\n\n".join(paragraph_group)
                    group_file = self.temp_dir / f"chapter_{chapter_num:03d}_group_{group_idx//self.paragraphs_per_group:03d}.mp3"
                    tasks.append((group_text, group_file, f"ch{chapter_num}_g{group_idx//self.paragraphs_per_group}"))
        
        return tasks
    
    def generate_audiobook_parallel(self, chapters):
        """Параллельная генерация аудиокниги"""
        print(f"\n🎙️ Начинаем генерацию аудиокниги...")
        print(f"   Голос: {self.selected_voice}")
        print(f"   Параллельных потоков: {self.workers}")
        print(f"   Глав: {len(chapters)}")
        print(f"   Параграфов в группе: {self.paragraphs_per_group}")
        
        # Пытаемся увеличить лимит файлов если возможно
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if soft < 4096:
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(4096, hard), hard))
                print(f"   Увеличен лимит файлов до {min(4096, hard)}")
        except:
            pass
        
        # Подготавливаем все задачи
        tasks = self.prepare_generation_tasks(chapters)
        print(f"   Фрагментов для генерации: {len(tasks)}")
        
        generated_files = {}
        failed_tasks = []
        
        # Создаем пул потоков для параллельной генерации с ограничением
        # Используем thread_name_prefix для отладки
        with ThreadPoolExecutor(
            max_workers=self.workers,
            thread_name_prefix="AudioGen"
        ) as executor:
            # Запускаем все задачи параллельно
            future_to_task = {
                executor.submit(self.generate_single_audio_sync, task): task
                for task in tasks
            }
            
            # Обрабатываем результаты по мере готовности
            with tqdm(total=len(tasks), desc="Генерация фрагментов") as pbar:
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        if result and result.exists():
                            # Сохраняем с ключом для правильной сортировки
                            output_file = task[1]
                            generated_files[str(output_file)] = output_file
                    except Exception as e:
                        chunk_id = task[2]
                        print(f"\n❌ Ошибка при генерации {chunk_id}: {e}")
                        failed_tasks.append(task)
                    finally:
                        pbar.update(1)
        
        if failed_tasks:
            print(f"\n⚠️ Не удалось сгенерировать {len(failed_tasks)} фрагментов")
            retry = input("   Попробовать еще раз с меньшим количеством потоков? (y/n): ")
            if retry.lower() == 'y':
                # Уменьшаем количество воркеров для повторной попытки
                retry_workers = max(1, min(5, self.workers // 2))
                print(f"   Повторная попытка с {retry_workers} потоками...")
                with ThreadPoolExecutor(
                    max_workers=retry_workers,
                    thread_name_prefix="AudioRetry"
                ) as executor:
                    for task in failed_tasks:
                        try:
                            result = executor.submit(self.generate_single_audio_sync, task).result()
                            if result and result.exists():
                                output_file = task[1]
                                generated_files[str(output_file)] = output_file
                        except Exception as e:
                            print(f"   ❌ Повторная ошибка: {e}")
        
        # Сортируем файлы по имени для правильного порядка
        sorted_files = sorted(generated_files.values(), key=lambda x: x.name)
        
        return sorted_files
    
    def create_audiobook(self, voice='male', rate="+0%", volume="+0%"):
        """Основная функция создания аудиокниги"""
        # Настраиваем параметры
        self.selected_voice = self.voices.get(voice, self.voices['male'])
        self.rate = rate
        self.volume = volume
        
        # Загружаем переводы
        chapters = self.load_translations()
        if not chapters:
            print("❌ Нет глав для озвучки")
            return False
        
        # Генерируем аудио параллельно
        audio_files = self.generate_audiobook_parallel(chapters)
        
        if not audio_files:
            print("❌ Не удалось сгенерировать аудио файлы")
            return False
        
        print(f"\n📀 Сгенерировано {len(audio_files)} аудио фрагментов")
        
        # Объединяем в финальную аудиокнигу
        final_audiobook = self.output_dir / "audiobook_complete.mp3"
        print(f"🎵 Объединяем в финальную аудиокнигу...")
        
        if self.merge_audio_files(audio_files, final_audiobook):
            print(f"✅ Аудиокнига создана: {final_audiobook}")
            
            # Получаем размер файла
            file_size = final_audiobook.stat().st_size / (1024 * 1024)  # В мегабайтах
            print(f"📊 Размер: {file_size:.1f} МБ")
            
            # Сохраняем метаданные
            self.save_metadata(len(chapters), len(audio_files))
            
            # Опционально: удаляем временные файлы
            if input("\n🗑️ Удалить временные аудио файлы? (y/n): ").lower() == 'y':
                self.cleanup_temp_files()
            
            return True
        else:
            print("❌ Не удалось создать финальную аудиокнигу")
            return False
    
    def cleanup_temp_files(self):
        """Удаление временных файлов"""
        print("🧹 Удаляем временные файлы...")
        for temp_file in self.temp_dir.glob("*.mp3"):
            temp_file.unlink()
        print("✅ Временные файлы удалены")
    
    def save_metadata(self, chapters_count, fragments_count):
        """Сохранение метаданных аудиокниги"""
        self.metadata['chapters_count'] = chapters_count
        self.metadata['fragments_count'] = fragments_count
        
        metadata_file = self.output_dir / "audiobook_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Генератор аудиокниги из переведенного текста')
    parser.add_argument('--voice', choices=['male', 'female'], default='male',
                       help='Голос для озвучки (по умолчанию: male)')
    parser.add_argument('--rate', default='+0%',
                       help='Скорость речи (-50%% до +100%%, по умолчанию: +0%%)')
    parser.add_argument('--volume', default='+0%',
                       help='Громкость (-50%% до +100%%, по умолчанию: +0%%)')
    parser.add_argument('--workers', type=int, default=25,
                       help='Количество параллельных потоков (по умолчанию: 25)')
    parser.add_argument('--paragraphs-per-group', type=int, default=3,
                       help='Количество параграфов в группе (по умолчанию: 3, как при переводе)')
    parser.add_argument('--disable-phonetic', action='store_true',
                       help='Отключить фонетическую замену английских терминов')
    parser.add_argument('--translations-dir', default='translations',
                       help='Директория с переводами (по умолчанию: translations)')
    parser.add_argument('--list-voices', action='store_true',
                       help='Показать доступные голоса')
    
    args = parser.parse_args()
    
    # Создаем генератор
    generator = AudioBookGenerator(
        translations_dir=args.translations_dir,
        workers=args.workers,
        paragraphs_per_group=args.paragraphs_per_group,
        enable_phonetic=not args.disable_phonetic
    )
    
    # Если запрошен список голосов
    if args.list_voices:
        generator.get_available_voices()
        return
    
    # Генерируем аудиокнигу
    print("🎧 Генератор аудиокниги v1.0")
    print("=" * 50)
    
    success = generator.create_audiobook(
        voice=args.voice,
        rate=args.rate,
        volume=args.volume
    )
    
    if success:
        print("\n🎉 Аудиокнига успешно создана!")
        print("📁 Файлы:")
        print(f"   • audiobook/audiobook_complete.mp3 - полная аудиокнига")
        print(f"   • audiobook/audiobook_metadata.json - метаданные")
    else:
        print("\n❌ Ошибка при создании аудиокниги")
        sys.exit(1)


if __name__ == "__main__":
    main()