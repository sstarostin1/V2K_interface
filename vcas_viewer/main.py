# -*- coding: utf-8 -*-
"""
VCAS Server Viewer - точка входа программы
Программа для просмотра архитектуры VCAS сервера ВЭПП-2000

Запуск в режиме тестового сервера: python -m vcas_viewer --mock

Документация: DOCS/04_Внутренние_процессы/Инициализация.md
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTranslator, QLocale
from PyQt5.QtGui import QFont

from .gui.main_window import MainWindow
from .core.config import Config
from .core.logging_config import parse_logging_args, configure_logging, finalize_session
import atexit
import logging


def setup_application():
    """Настройка приложения"""
    # Обрабатываем аргументы командной строки для режима заглушки
    mock_mode = False
    for arg in sys.argv[1:]:
        if arg in ['--mock-server', '--mock', '--test']:
            mock_mode = True
            break

    # Устанавливаем переменную окружения для режима заглушки
    if mock_mode:
        os.environ['VCAS_MOCK_MODE'] = '1'

    # Создаем QApplication
    app = QApplication(sys.argv)

    # Настройка основных параметров приложения
    app.setApplicationName("VCAS Server Viewer")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("ВЭПП-2000")
    app.setOrganizationDomain("vepp2000.ru")

    # Настройка шрифтов для лучшего отображения
    font = QFont("Consolas", 9)
    app.setFont(font)

    # Настройка стиля интерфейса (нативный для системы)
    app.setStyle('Fusion')

    return app


def setup_exception_handling():
    """Настройка обработки исключений"""
    def exception_hook(exctype, value, traceback):
        logging.critical("Необработанное исключение",
                        exc_info=(exctype, value, traceback))

    sys.excepthook = exception_hook


def main():
    """Главная функция программы"""
    try:
        # Логирование уже настроено в main.py, регистрируем финализатор сессии
        atexit.register(finalize_session)

        # Настройка обработки исключений
        setup_exception_handling()

        # Создание и настройка приложения
        app = setup_application()

        # Создание главного окна
        main_window = MainWindow()

        # Показываем окно
        main_window.show()

        # Запуск главного цикла приложения
        exit_code = app.exec_()

        # Возврат кода завершения
        return exit_code

    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске программы: {str(e)}")
        return 1


if __name__ == "__main__":
    # Запуск программы
    sys.exit(main())
