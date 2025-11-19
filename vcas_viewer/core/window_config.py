# -*- coding: utf-8 -*-
"""
WindowConfig - система конфигурации окон графиков
"""

import json
import os
import logging
from typing import Dict, List, Optional
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtWidgets import QSplitter
import sys
import os as os_module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from vcas_viewer.plotting.plot_settings_panel import PlotSettings, FillMode


class DockWindowConfig:
    """
    Конфигурация окна графиков
    """
    def __init__(self):
        self.geometry: Optional[QRect] = None
        self.plot_settings: Dict[str, PlotSettings] = {}  # channel_name -> settings
        self.visible_channels: List[str] = []
        self.layout_orientation: Qt.Orientation = Qt.Vertical
        self.splitter_sizes: List[int] = []

    def to_dict(self) -> dict:
        """
        Преобразовать в словарь для сериализации

        Returns:
            Словарь с данными конфигурации
        """
        return {
            'geometry': {
                'x': self.geometry.x() if self.geometry else 0,
                'y': self.geometry.y() if self.geometry else 0,
                'width': self.geometry.width() if self.geometry else 800,
                'height': self.geometry.height() if self.geometry else 600
            } if self.geometry else None,
            'plot_settings': {
                channel: {
                    'time_window_minutes': settings.time_window_minutes,
                    'fill_mode': settings.fill_mode
                }
                for channel, settings in self.plot_settings.items()
            },
            'visible_channels': self.visible_channels,
            'layout_orientation': self.layout_orientation,
            'splitter_sizes': self.splitter_sizes
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DockWindowConfig':
        """
        Создать объект из словаря

        Args:
            data: Словарь с данными конфигурации

        Returns:
            Объект DockWindowConfig
        """
        config = cls()

        # Геометрия
        if data.get('geometry'):
            geom = data['geometry']
            config.geometry = QRect(geom['x'], geom['y'], geom['width'], geom['height'])

        # Настройки графиков
        if data.get('plot_settings'):
            for channel, settings_data in data['plot_settings'].items():
                settings = PlotSettings(
                    time_window_minutes=settings_data.get('time_window_minutes', 5),
                    fill_mode=settings_data.get('fill_mode', FillMode.ROLLING_RIGHT)
                )
                config.plot_settings[channel] = settings

        # Видимые каналы
        config.visible_channels = data.get('visible_channels', [])

        # Ориентация layout
        config.layout_orientation = data.get('layout_orientation', Qt.Vertical)

        # Размеры сплиттера
        config.splitter_sizes = data.get('splitter_sizes', [])

        return config


class WindowConfig:
    """
    Менеджер конфигурации окон
    """

    def __init__(self, config_dir: str = None):
        self.logger = logging.getLogger('WindowConfig')

        if config_dir is None:
            # Директория для конфигураций окон
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.config_dir = os.path.join(base_dir, 'window_configs')
        else:
            self.config_dir = config_dir

        # Создаем директорию если не существует
        os.makedirs(self.config_dir, exist_ok=True)

        self.logger.debug(f"WindowConfig инициализирован, директория: {self.config_dir}")

    def save_window_config(self, window_id: str, config: DockWindowConfig):
        """
        Сохранить конфигурацию окна

        Args:
            window_id: Идентификатор окна
            config: Конфигурация окна
        """
        try:
            config_path = os.path.join(self.config_dir, f"{window_id}.json")

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)

            self.logger.info(f"Конфигурация окна {window_id} сохранена")

        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации окна {window_id}: {e}")

    def load_window_config(self, window_id: str) -> Optional[DockWindowConfig]:
        """
        Загрузить конфигурацию окна

        Args:
            window_id: Идентификатор окна

        Returns:
            Конфигурация окна или None если не найдена
        """
        try:
            config_path = os.path.join(self.config_dir, f"{window_id}.json")

            if not os.path.exists(config_path):
                self.logger.debug(f"Конфигурация окна {window_id} не найдена")
                return None

            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            config = DockWindowConfig.from_dict(data)
            self.logger.info(f"Конфигурация окна {window_id} загружена")
            return config

        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации окна {window_id}: {e}")
            return None

    def delete_window_config(self, window_id: str):
        """
        Удалить конфигурацию окна

        Args:
            window_id: Идентификатор окна
        """
        try:
            config_path = os.path.join(self.config_dir, f"{window_id}.json")

            if os.path.exists(config_path):
                os.remove(config_path)
                self.logger.info(f"Конфигурация окна {window_id} удалена")
            else:
                self.logger.debug(f"Конфигурация окна {window_id} не найдена для удаления")

        except Exception as e:
            self.logger.error(f"Ошибка удаления конфигурации окна {window_id}: {e}")

    def list_window_configs(self) -> List[str]:
        """
        Получить список сохраненных конфигураций окон

        Returns:
            Список идентификаторов окон
        """
        try:
            if not os.path.exists(self.config_dir):
                return []

            configs = []
            for filename in os.listdir(self.config_dir):
                if filename.endswith('.json'):
                    window_id = filename[:-5]  # Убираем .json
                    configs.append(window_id)

            return configs

        except Exception as e:
            self.logger.error(f"Ошибка получения списка конфигураций: {e}")
            return []
