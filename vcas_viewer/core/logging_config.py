"""
Централизованное управление настройками логирования для VCAS Viewer.

Модуль предоставляет функции для парсинга уровня логирования из командной строки
и настройки глобального поведения логгера с пятью предопределенными уровнями:
- minimal: WARNING и выше (тихий режим по умолчанию для консоли и файла)
- concise: INFO и выше (основная информация)
- full: DEBUG и выше (отладочная информация)
- trace: TRACE и выше (максимальная детализация)
- none: ничего не логируется в файл, но создается файл с временем завершения сеанса
"""

import logging
import sys
import re
from typing import Optional
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Один TRACE уровень ниже DEBUG
TRACE_LEVEL = 5
logging.addLevelName(TRACE_LEVEL, 'TRACE')

# NONE уровень выше CRITICAL - ничего не логируется
NONE_LEVEL = logging.CRITICAL + 10

LOG_LEVELS = {
    'minimal': logging.WARNING,    # 30
    'concise': logging.INFO,       # 20
    'full': logging.DEBUG,         # 10
    'trace': TRACE_LEVEL,          # 5
    'none': NONE_LEVEL             # 60 (выше CRITICAL, ничего не логируется)
}

# Дефолты по умолчанию
DEFAULT_CONSOLE_LEVEL = 'minimal'
DEFAULT_FILE_LEVEL = 'minimal'

# Глобальная переменная для сессионного file handler (для финализации)
_session_file_handler = None


class MillisecondsFormatter(logging.Formatter):
    """
    Кастомный Formatter для добавления миллисекунд в таймстампы.

    Расширяет стандартный Formatter для обработки %f с обрезкой до миллисекунд.
    """

    def formatTime(self, record, datefmt=None):
        if datefmt and '%f' in datefmt:
            import time
            ct = self.converter(record.created)
            separator = ',' if ',' in datefmt else '.'
            base_str = time.strftime(datefmt.replace(',', '').replace('%f', ''), ct)
            s = base_str + separator + '%03d' % record.msecs
            return s
        else:
            return super().formatTime(record, datefmt)


class LoggingStatsHandler(logging.FileHandler):
    """
    Кастомный FileHandler с подсчетом статистики сообщений и единообразным форматированием времени с миллисекундами.
    """

    def __init__(self, filename, mode='a', encoding='utf-8'):
        super().__init__(filename, mode=mode, encoding=encoding)
        self.message_counts = {}  # Словарь для подсчета сообщений по уровням

        # Создаем единый форматтер с миллисекундами для всех записей
        self.formatter = MillisecondsFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S,%f'  # Единый формат времени с миллисекундами
        )

    def emit(self, record):
        """Переопределенный метод emit для подсчета статистики с единообразным форматированием."""
        # Подсчет сообщений по уровням
        level_name = getattr(record, 'levelname', str(record.levelno))
        self.message_counts[level_name] = self.message_counts.get(level_name, 0) + 1

        # Устанавливаем единый форматтер с миллисекундами для всех записей
        self.setFormatter(self.formatter)

        # Вызываем родительский emit
        super().emit(record)

    def get_statistics(self):
        """Возвращает статистику по сообщениям."""
        return self.message_counts.copy()


def get_logging_level_from_string(level_str: str) -> int:
    """
    Преобразует строку уровня логирования в соответствующий уровень logging.

    Args:
        level_str: Строка, представляющая уровень ('minimal', 'concise', 'full')

    Returns:
        Уровень logging модуля

    Raises:
        ValueError: Если передана неподдерживаемая строка уровня
    """
    if level_str not in LOG_LEVELS:
        raise ValueError(
            f"Неподдерживаемый уровень логирования: '{level_str}'. "
            f"Допустимые значения: {', '.join(LOG_LEVELS.keys())}"
        )
    return LOG_LEVELS[level_str]


def parse_logging_level(args: Optional[list] = None) -> str:
    """
    Парсит уровень логирования из аргументов командной строки.

    Ищет аргументы --logging или --log-level и возвращает соответствующий уровень.
    По умолчанию возвращает 'minimal' (тихий режим).

    Поддерживает старые имена уровней для обратной совместимости:
    - 'debug' -> 'full'
    - 'info' -> 'concise'
    - 'warning' -> 'minimal'

    Args:
        args: Список аргументов командной строки (по умолчанию sys.argv[1:])

    Returns:
        Строковое представление уровня логирования
    """
    if args is None:
        args = sys.argv[1:]

    # Маппинг старых имен на новые для обратной совместимости
    level_aliases = {
        'debug': 'full',
        'info': 'concise',
        'warning': 'minimal',
        'error': 'minimal',  # error и выше всегда показываем
        'critical': 'minimal'
    }

    for i, arg in enumerate(args):
        if arg in ['--logging', '--log-level']:
            if i + 1 < len(args):
                level_str = args[i + 1].lower()
                # Сначала проверяем в основных уровнях
                if level_str in LOG_LEVELS:
                    return level_str
                # Затем проверяем алиасы
                elif level_str in level_aliases:
                    return level_aliases[level_str]
                else:
                    print(
                        f"Предупреждение: неподдерживаемый уровень логирования '{level_str}'. "
                        f"Используется уровень по умолчанию 'minimal'. "
                        f"Допустимые значения: {', '.join(LOG_LEVELS.keys())}",
                        file=sys.stderr
                    )
                    return 'minimal'
            else:
                print("Предупреждение: аргумент --logging требует значения.", file=sys.stderr)
                return 'minimal'

    return 'minimal'


def configure_logging(console_level: str, file_level: str) -> None:
    """
    Настраивает глобальное логирование с разделением по выходам.

    Создает отдельные handlers для консоли и файла с сессионным именем.
    Устанавливает уровень root логгера на TRACE для максимальной детализации.

    Args:
        console_level: Уровень логирования для консольного вывода
        file_level: Уровень логирования для файлового вывода
    """
    global _session_file_handler

    # Создаем root logger
    logger = logging.getLogger()
    logger.setLevel(TRACE_LEVEL)  # Минимальный уровень (TRACE) для root логгера

    # Handler для консоли (краткий формат времени)
    console_formatter = MillisecondsFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S,%f'  # Короткий формат для консоли с миллисекундами
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(get_logging_level_from_string(console_level))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Handler для файла (сессионный с подсчетом статистики)
    log_dir = Path('logs')
    try:
        log_dir.mkdir(exist_ok=True)
    except (OSError, PermissionError) as e:
        print(f"Предупреждение: не удалось создать директорию logs: {e}. "
              f"Логи будут записываться в текущую директорию.", file=sys.stderr)
        log_dir = Path('.')

    session_filename = generate_session_filename()
    session_file_path = log_dir / session_filename

    try:
        file_handler = LoggingStatsHandler(session_file_path, encoding='utf-8')
        file_handler.setLevel(get_logging_level_from_string(file_level))
        logger.addHandler(file_handler)

        # Сохраняем reference для финализации
        _session_file_handler = file_handler

        # Сообщаем о настройках логирования
        session_logger = logging.getLogger('VCAS.Session')
        session_logger.info(f"Session started - console: {console_level}, file: {file_level}")
        session_logger.info(f"Log file: {session_file_path.absolute()}")

    except (OSError, PermissionError) as e:
        print(f"Ошибка: не удалось создать файл логов {session_file_path}: {e}", file=sys.stderr)
        print("Логирование в файл отключено.", file=sys.stderr)
        _session_file_handler = None


def get_current_log_level() -> str:
    """
    Возвращает текущий уровень логирования в строковом формате.

    Returns:
        Текущий уровень как строка ('minimal', 'concise', 'full', 'trace')
    """
    current_level = logging.root.level
    for name, level in LOG_LEVELS.items():
        if level == current_level:
            return name
    return 'unknown'


def generate_session_filename() -> str:
    """
    Генерирует уникальное имя файла для сессии на основе текущего времени.

    Использует временную зону Asia/Bangkok и формат dd-mm-YYYY_HH-MM-SS.

    Returns:
        Имя файла в формате 'session_dd-mm-YYYY_HH-MM-SS.log'
    """
    tz = ZoneInfo('Asia/Bangkok')
    now = datetime.now(tz)
    return f"session_{now.strftime('%d-%m-%Y_%H-%M-%S')}.log"


def parse_console_logging_level(args: Optional[list] = None) -> str:
    """
    Парсит уровень логирования для консольного вывода из аргументов командной строки.

    Args:
        args: Список аргументов командной строки

    Returns:
        Уровень логирования для консоли
    """
    if args is None:
        args = sys.argv[1:]

    for i, arg in enumerate(args):
        if arg == '--console-logging':
            if i + 1 < len(args):
                level_str = args[i + 1].lower()
                if level_str in LOG_LEVELS:
                    return level_str
                else:
                    print(
                        f"Предупреждение: неподдерживаемый уровень логирования '{level_str}' для консоли. "
                        f"Используется уровень по умолчанию '{DEFAULT_CONSOLE_LEVEL}'. "
                        f"Допустимые значения: {', '.join(LOG_LEVELS.keys())}",
                        file=sys.stderr
                    )
                    return DEFAULT_CONSOLE_LEVEL
            else:
                print("Предупреждение: аргумент --console-logging требует значения.", file=sys.stderr)
                return DEFAULT_CONSOLE_LEVEL

    return DEFAULT_CONSOLE_LEVEL


def parse_file_logging_level(args: Optional[list] = None) -> str:
    """
    Парсит уровень логирования для файлового вывода из аргументов командной строки.

    Args:
        args: Список аргументов командной строки

    Returns:
        Уровень логирования для файла
    """
    if args is None:
        args = sys.argv[1:]

    for i, arg in enumerate(args):
        if arg == '--file-logging':
            if i + 1 < len(args):
                level_str = args[i + 1].lower()
                if level_str in LOG_LEVELS:
                    return level_str
                else:
                    print(
                        f"Предупреждение: неподдерживаемый уровень логирования '{level_str}' для файла. "
                        f"Используется уровень по умолчанию '{DEFAULT_FILE_LEVEL}'. "
                        f"Допустимые значения: {', '.join(LOG_LEVELS.keys())}",
                        file=sys.stderr
                    )
                    return DEFAULT_FILE_LEVEL
            else:
                print("Предупреждение: аргумент --file-logging требует значения.", file=sys.stderr)
                return DEFAULT_FILE_LEVEL

    return DEFAULT_FILE_LEVEL


def parse_logging_args(args: Optional[list] = None) -> tuple[str, str]:
    """
    Парсит уровни логирования для консоли и файла из аргументов командной строки.

    Поддерживает как раздельное управление (--console-logging и --file-logging),
    так и совместимость с --logging (применяет к обоим).

    Args:
        args: Список аргументов командной строки

    Returns:
        Кортеж (console_level, file_level)
    """
    if args is None:
        args = sys.argv[1:]

    # Сначала проверяем старый аргумент --logging для обратной совместимости
    legacy_level = parse_logging_level(args)
    if legacy_level != DEFAULT_CONSOLE_LEVEL or '--logging' in args:
        # Если указан --logging, применяем его к обоим
        return legacy_level, legacy_level

    # Иначе парсим раздельно
    console_level = parse_console_logging_level(args)
    file_level = parse_file_logging_level(args)

    return console_level, file_level


def finalize_session():
    """
    Записывает время завершения сессии в лог-файл и отчет по статистике.

    Вызывается при штатном завершении программы для фиксации
    времени окончания работы в сессионном файле логов.
    Всегда записывает время завершения и отчет по сообщениям независимо от уровня логирования файла.
    """
    global _session_file_handler

    if _session_file_handler is None:
        return

    try:
        # Получаем текущее время в Bangkok timezone
        tz = ZoneInfo('Asia/Bangkok')
        now = datetime.now(tz)

        # Создаем временный logger только для записи в файл сессии
        session_logger = logging.getLogger('VCAS.Session.End')
        # Убеждаемся, что у логгера нет других handlers
        session_logger.handlers.clear()
        # Добавляем наш сессионный file handler
        session_logger.addHandler(_session_file_handler)

        # Сохраняем оригинальный уровень handler'a
        original_level = _session_file_handler.level

        # Временно устанавливаем уровень для гарантированной записи
        _session_file_handler.setLevel(TRACE_LEVEL)

        # Устанавливаем уровень логгера
        session_logger.setLevel(TRACE_LEVEL)
        # Запрещаем propagation, чтобы не дублировалось в другие handlers
        session_logger.propagate = False

        # Записываем время завершения
        session_logger.info(f"Session ended at {now.strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]}")

        # Добавляем разделитель
        session_logger.info("=" * 60)

        # Получаем и записываем статистику сообщений
        if hasattr(_session_file_handler, 'get_statistics'):
            stats = _session_file_handler.get_statistics()
            if stats:
                session_logger.info("Session Statistics:")
                session_logger.info("LEVEL      | COUNT")
                session_logger.info("-" * 18)

                # Сортируем уровни по имени для аккуратного отчета
                sorted_levels = sorted(stats.items(), key=lambda x: (LOG_LEVELS.get(x[0], 999), x[0]))

                for level_name, count in sorted_levels:
                    session_logger.info(f"{level_name:<10} | {count}")

                total_messages = sum(stats.values())
                session_logger.info("-" * 18)
                session_logger.info(f"TOTAL      | {total_messages}")
            else:
                session_logger.info("No messages were logged during this session.")

        session_logger.info("=" * 60)

        # Восстанавливаем оригинальный уровень handler'a
        _session_file_handler.setLevel(original_level)

        # Закрываем handler
        _session_file_handler.close()
        _session_file_handler = None

    except Exception as e:
        # В случае ошибки финализации пишем в stderr, но не выбрасываем исключение
        print(f"Предупреждение: ошибка при финализации логов сессии: {e}", file=sys.stderr)
