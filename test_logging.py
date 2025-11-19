#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки новой системы логирования
"""

from vcas_viewer.core.logging_config import (
    parse_logging_args,
    generate_session_filename,
    configure_logging,
    finalize_session
)

def test_parse_logging_args():
    """Тестирование парсинга аргументов"""
    print("=== Тестирование парсинга аргументов ===")

    # Тест 1: по умолчанию
    result = parse_logging_args([])
    print(f"По умолчанию: {result} (ожидается: ('minimal', 'trace'))")

    # Тест 2: раздельные аргументы
    result = parse_logging_args(['--console-logging', 'concise', '--file-logging', 'full'])
    print(f"Раздельные: {result} (ожидается: ('concise', 'full'))")

    # Тест 3: обратная совместимость
    result = parse_logging_args(['--logging', 'debug'])
    print(f"Обратная совместимость: {result} (ожидается: ('full', 'full'))")

    print()

def test_session_filename():
    """Тестирование генерации имени файла сессии"""
    print("=== Тестирование генерации имени файла ===")

    filename = generate_session_filename()
    print(f"Сгенерированное имя: {filename}")

    # Проверка формата
    if filename.startswith('session_') and filename.endswith('.log'):
        print("+ Формат имени корректный")
    else:
        print("- Формат имени некорректный")

    print()

def test_configure_logging():
    """Тестирование настройки логирования"""
    print("=== Тестирование настройки логирования ===")

    try:
        # Запомним время начала (до настройки логирования)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        start_time = datetime.now(ZoneInfo('Asia/Bangkok'))

        configure_logging('minimal', 'trace')
        print("+ Настройка логирования прошла успешно")

        # Проверим, создалась ли директория logs
        import os
        if os.path.exists('logs'):
            print("+ Директория logs создана")
            files = os.listdir('logs')

            # Найдем самый свежий файл (созданный после start_time)
            latest_file = None
            latest_time = None
            for filename in files:
                if filename.startswith('session_') and filename.endswith('.log'):
                    file_path = os.path.join('logs', filename)
                    file_mtime = os.path.getmtime(file_path)
                    if latest_time is None or file_mtime > latest_time:
                        latest_time = file_mtime
                        latest_file = filename

            if latest_file:
                print(f"+ Найден свежий файл сессии: {latest_file}")

                # Финализируем сессию
                finalize_session()
                print("+ Финализация сессии выполнена")

                # Проверим последнюю строку в файле
                log_file = os.path.join('logs', latest_file)
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        if 'Session ended at' in last_line:
                            print("+ Время завершения записано корректно")
                            print(f"  Последняя строка: {last_line}")
                        else:
                            print("- Время завершения не найдено")
                            print(f"  Содержимое файла:")
                            for line in lines[-3:]:  # последние 3 строки
                                print(f"    {line.strip()}")
                    else:
                        print("- Файл логов пустой")
            else:
                print("- Файл сессии не найден")

        else:
            print("? Директория logs не найдена")

    except Exception as e:
        print(f"- Ошибка настройки логирования: {e}")

    print()

if __name__ == '__main__':
    test_parse_logging_args()
    test_session_filename()
    test_configure_logging()
