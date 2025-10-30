#!/usr/bin/env python3
"""
Монитор состояния Ollama - показывает активные процессы и загрузку
"""

import requests
import json
import time
import sys
from datetime import datetime, timedelta
import subprocess
import psutil

def get_ollama_status():
    """Получает статус Ollama через API"""
    try:
        # Проверяем запущенные модели
        ps_response = requests.get('http://localhost:11434/api/ps', timeout=2)
        ps_data = ps_response.json()
        
        return ps_data
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}

def get_system_stats():
    """Получает системную статистику"""
    stats = {
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'memory_percent': psutil.virtual_memory().percent,
        'memory_used_gb': psutil.virtual_memory().used / (1024**3),
        'memory_total_gb': psutil.virtual_memory().total / (1024**3)
    }
    return stats

def format_time_delta(expires_at_str):
    """Форматирует время до истечения"""
    try:
        # Парсим ISO время
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        now = datetime.now(expires_at.tzinfo)
        delta = expires_at - now
        
        if delta.total_seconds() > 0:
            minutes = int(delta.total_seconds() / 60)
            seconds = int(delta.total_seconds() % 60)
            return f"{minutes}:{seconds:02d}"
        else:
            return "истекло"
    except:
        return "неизвестно"

def format_size(size_bytes):
    """Форматирует размер в читаемый вид"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def check_ollama_logs():
    """Проверяет логи Ollama"""
    try:
        # Пытаемся получить последние строки из логов
        result = subprocess.run(
            ['tail', '-n', '20', '/tmp/ollama.log'],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout
    except:
        pass
    
    # Альтернативный способ - через journalctl
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'ollama', '-n', '20', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout
    except:
        pass
    
    return None

def monitor_loop(interval=1):
    """Основной цикл мониторинга"""
    print("\033[2J\033[H")  # Очистка экрана
    print("🔍 МОНИТОР OLLAMA")
    print("=" * 60)
    
    log_messages = []
    
    try:
        while True:
            # Очистка экрана и перемещение курсора
            print("\033[H")
            
            # Заголовок
            print("🔍 МОНИТОР OLLAMA".ljust(60))
            print("=" * 60)
            print(f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            # Системная статистика
            sys_stats = get_system_stats()
            print("📊 СИСТЕМА:")
            print(f"   CPU: {sys_stats['cpu_percent']:5.1f}%")
            print(f"   RAM: {sys_stats['memory_used_gb']:.1f}/{sys_stats['memory_total_gb']:.1f} GB ({sys_stats['memory_percent']:.1f}%)")
            print()
            
            # Статус Ollama
            status = get_ollama_status()
            
            if "error" in status:
                print("❌ ОШИБКА ПОДКЛЮЧЕНИЯ К OLLAMA:")
                print(f"   {status['error']}")
                print()
                print("💡 Проверьте что Ollama запущена:")
                print("   ollama serve")
            else:
                models = status.get("models", [])
                
                if models:
                    print(f"🤖 АКТИВНЫЕ МОДЕЛИ ({len(models)}):")
                    print()
                    
                    for i, model in enumerate(models, 1):
                        name = model.get("name", "неизвестно")
                        size = model.get("size", 0)
                        size_vram = model.get("size_vram", 0)
                        context_len = model.get("context_length", 0)
                        expires = model.get("expires_at", "")
                        
                        print(f"   [{i}] {name}")
                        print(f"       📦 Размер в памяти: {format_size(size)}")
                        print(f"       🎮 VRAM: {format_size(size_vram)}")
                        print(f"       📝 Контекст: {context_len} токенов")
                        print(f"       ⏱️  Истекает через: {format_time_delta(expires)}")
                        
                        # Детали модели
                        details = model.get("details", {})
                        if details:
                            param_size = details.get("parameter_size", "")
                            quant = details.get("quantization_level", "")
                            if param_size or quant:
                                print(f"       🔧 Параметры: {param_size} / {quant}")
                        print()
                else:
                    print("💤 НЕТ АКТИВНЫХ МОДЕЛЕЙ")
                    print()
                    print("Модели автоматически выгружаются через 5 минут неактивности.")
                    print()
            
            # Проверка процессов
            print("🔄 ПРОЦЕССЫ:")
            ollama_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                if 'ollama' in proc.info['name'].lower():
                    ollama_procs.append(proc)
            
            if ollama_procs:
                for proc in ollama_procs:
                    try:
                        print(f"   PID {proc.pid}: {proc.info['name']} | CPU: {proc.cpu_percent():.1f}% | RAM: {proc.memory_percent():.1f}%")
                    except:
                        pass
            else:
                print("   Процессы Ollama не найдены")
            
            print()
            print("-" * 60)
            print("Нажмите Ctrl+C для выхода | Обновление каждую секунду")
            
            # Ждем
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Мониторинг остановлен")
        return

def check_active_requests():
    """Проверка активных запросов через альтернативные методы"""
    print("\n🔍 ПРОВЕРКА АКТИВНОСТИ:")
    print("-" * 40)
    
    # Метод 1: Проверка через netstat
    try:
        result = subprocess.run(
            ['netstat', '-an'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            ollama_connections = [l for l in lines if '11434' in l and 'ESTABLISHED' in l]
            if ollama_connections:
                print(f"📡 Активные подключения к Ollama: {len(ollama_connections)}")
                for conn in ollama_connections[:5]:
                    print(f"   {conn[:80]}")
            else:
                print("📡 Нет активных подключений к порту 11434")
    except:
        pass
    
    # Метод 2: Проверка загрузки CPU процессом
    print("\n💻 ЗАГРУЗКА ПРОЦЕССОРА:")
    try:
        result = subprocess.run(
            ['top', '-l', '1', '-n', '5'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if 'ollama' in line.lower():
                    print(f"   {line[:100]}")
    except:
        pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Монитор состояния Ollama')
    parser.add_argument('--once', '-o', action='store_true', help='Показать статус один раз и выйти')
    parser.add_argument('--interval', '-i', type=int, default=1, help='Интервал обновления в секундах')
    parser.add_argument('--check', '-c', action='store_true', help='Проверить активные подключения')
    
    args = parser.parse_args()
    
    if args.once:
        status = get_ollama_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    elif args.check:
        check_active_requests()
    else:
        monitor_loop(args.interval)

if __name__ == "__main__":
    main()