# -*- coding: utf-8 -*-
"""
Конфигурация VCAS Viewer
"""

import os
import json

class Config:
    """Класс конфигурации приложения"""

    # Флаг для использования mock сервера (устанавливается из командной строки)
    _mock_server_flag = False

    # Параметры подключения к VCAS серверу
    VCAS_HOST = "172.16.1.110"
    VCAS_PORT = 20041

    # Параметры подключения к Mock VCAS серверу (для отладки)
    MOCK_VCAS_HOST = "127.0.0.1"
    MOCK_VCAS_PORT = 20042

    # Режим работы (определяется переменной окружения или параметром командной строки)
    @classmethod
    def use_mock_server(cls):
        """Проверить, нужно ли использовать тестовый сервер"""
        return os.getenv('VCAS_MOCK_MODE', '0').lower() in ('1', 'true', 'yes') or cls._mock_server_flag

    @classmethod
    def set_mock_server(cls, use_mock: bool):
        """Установить флаг использования mock сервера"""
        cls._mock_server_flag = use_mock

    # Настройки интерфейса
    WINDOW_TITLE = "VCAS Server Viewer"
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 700

    SELECTION_MODE = 'Single'  # Single, Multi, Range
    EXPANDED_DIRS = []  # Список раскрытых директорий для сохранения состояния

    # Время ожидания подключения (секунды)
    CONNECTION_TIMEOUT = 5

    # Время обновления списка каналов (секунды)
    CHANNELS_UPDATE_INTERVAL = 30

    # Настройки графиков
    GRAPH_UPDATE_INTERVAL = 1.0  # Интервал обновления графиков в секундах (по умолчанию)
    GRAPH_MAX_POINTS = 1000  # Максимальное количество точек на канал
    GRAPH_TIME_WINDOWS = [1, 5, 10, 30]  # Доступные окна времени в минутах
    GRAPH_DEFAULT_TIME_WINDOW = 5  # Окно времени по умолчанию в минутах
    GRAPH_DISPLAY_MODES = ['Сканирование слева', 'Скользящее справа']  # Режимы отображения
    GRAPH_DEFAULT_DISPLAY_MODE = 'Скользящее справа'  # Режим отображения по умолчанию
    GRAPH_CHANNEL_COLORS = ['#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
                           '#800000', '#008000', '#000080', '#808000', '#800080', '#008080']  # Цвета кривых для каналов

    @classmethod
    def get_vcas_address(cls):
        """Получить адрес VCAS сервера (реальный или mock)"""
        if cls.use_mock_server():
            return (cls.MOCK_VCAS_HOST, cls.MOCK_VCAS_PORT)
        else:
            return (cls.VCAS_HOST, cls.VCAS_PORT)

    @classmethod
    def get_window_size(cls):
        """Получить размер главного окна"""
        return (cls.WINDOW_WIDTH, cls.WINDOW_HEIGHT)

    @classmethod
    def is_mock_mode(cls):
        """Проверить, используется ли режим заглушки"""
        return cls.use_mock_server()

    # Путь к файлу конфигурации
    CONFIG_FILE = os.path.join(os.getcwd(), 'config.json')

    @classmethod
    def save_config(cls):
        """Сохранить текущие настройки в JSON файл"""
        config_data = {
            'selection_mode': cls.SELECTION_MODE,
            'expanded_dirs': cls.EXPANDED_DIRS
        }
        try:
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")

    @classmethod
    def load_config(cls):
        """Загрузить настройки из JSON файла"""
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                cls.SELECTION_MODE = config_data.get('selection_mode', cls.SELECTION_MODE)
                cls.EXPANDED_DIRS = config_data.get('expanded_dirs', cls.EXPANDED_DIRS)
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
