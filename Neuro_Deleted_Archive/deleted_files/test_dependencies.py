#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки зависимостей
"""

def test_imports():
    """Проверка импортов необходимых модулей"""
    try:
        import PyQt5
        print("[OK] PyQt5 установлен")
    except ImportError as e:
        print(f"[ERROR] PyQt5 не установлен: {e}")
        return False

    try:
        import PyQt5.QtCore
        import PyQt5.QtWidgets
        import PyQt5.QtGui
        print("[OK] Все модули PyQt5 доступны")
    except ImportError as e:
        print(f"[ERROR] Некоторые модули PyQt5 недоступны: {e}")
        return False

    # Проверяем PyQtVChannels
    try:
        import PyQtVChannels
        print("[OK] PyQtVChannels установлен")
    except ImportError as e:
        print(f"[ERROR] PyQtVChannels не установлен: {e}")
        print("  Установите библиотеку: pip install PyQtVChannels")
        return False

    return True

def test_syntax():
    """Проверка синтаксиса основных файлов"""
    files_to_check = [
        'main.py',
        'main_window.py',
        'vcas_client.py',
        'config.py'
    ]

    all_good = True
    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            compile(content, file_path, 'exec')
            print(f"[OK] Синтаксис {file_path} корректен")
        except SyntaxError as e:
            print(f"[ERROR] Синтаксическая ошибка в {file_path}: {e}")
            all_good = False
        except FileNotFoundError:
            print(f"[ERROR] Файл {file_path} не найден")
            all_good = False
        except Exception as e:
            print(f"[ERROR] Ошибка при проверке {file_path}: {e}")
            all_good = False

    return all_good

def main():
    """Главная функция тестирования"""
    print("=== Проверка зависимостей VCAS Server Viewer ===\n")

    print("1. Проверка импортов:")
    imports_ok = test_imports()

    print("\n2. Проверка синтаксиса файлов:")
    syntax_ok = test_syntax()

    print("\n=== Результаты ===")
    if imports_ok and syntax_ok:
        print("[SUCCESS] Все проверки пройдены успешно!")
        print("Программа готова к запуску.")
        return 0
    else:
        print("[FAIL] Некоторые проверки не пройдены.")
        print("Установите недостающие зависимости и исправьте ошибки.")
        return 1

if __name__ == "__main__":
    exit(main())
