# -*- coding: utf-8 -*-
"""
PlotDockWindow - доковое окно для отображения графиков с поддержкой drag-and-drop
"""

from PyQt5.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame, QMenu, QAction, QLabel, QDoubleSpinBox
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QIcon, QPalette, QColor
import logging
import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from vcas_viewer.plotting.plot_container import PlotContainer
from vcas_viewer.models.channel_data import ChannelData
from vcas_viewer.core.config import Config
from vcas_viewer.core.window_config import WindowConfig, DockWindowConfig


class PlotDockWindow(QDockWidget):
    """
    Доковое окно для отображения графиков каналов с поддержкой drag-and-drop
    """

    # Сигналы
    channel_requested = pyqtSignal(str)  # Запрос данных канала
    window_closed = pyqtSignal()  # Окно закрыто
    settings_changed = pyqtSignal()  # Настройки окна изменены

    def __init__(self, title="Графики каналов", parent=None):
        super().__init__(title, parent)
        self.logger = logging.getLogger('PlotDockWindow')

        # Настройки
        self.channels_list = []  # Список каналов для отображения

        # Конфигурация окна
        self.window_config = WindowConfig()
        self.window_id = str(uuid.uuid4())  # Уникальный ID окна
        self.current_config = DockWindowConfig()

        self.setup_ui()
        self.setup_connections()

        # Загружаем конфигурацию окна
        self.load_config()

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable |
                        QDockWidget.DockWidgetClosable)

        # Центральный виджет
        central_widget = QWidget()
        self.setWidget(central_widget)

        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Создаем контейнер графиков
        self.plot_container = PlotContainer()
        main_layout.addWidget(self.plot_container)

        # Панель управления (видима по умолчанию)
        self.control_panel = self._create_control_panel()
        main_layout.addWidget(self.control_panel)

        # Настройка контекстного меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def setup_connections(self):
        """Настройка соединений сигналов"""
        # Соединения с контейнером графиков
        self.plot_container.channel_moved.connect(self._on_channel_moved)
        self.plot_container.plot_added.connect(self._on_plot_added)
        self.plot_container.plot_removed.connect(self._on_plot_removed)

        # Соединения с графиками
        for plot_widget in self.plot_container.plot_widgets:
            plot_widget.settings_changed.connect(self._on_plot_settings_changed)

    def _create_control_panel(self) -> QWidget:
        """
        Создать панель управления

        Returns:
            Виджет панели управления
        """
        panel = QWidget()
        panel.setStyleSheet("QWidget { background-color: #f0f0f0; border-top: 1px solid #ccc; padding: 5px; }")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)

        # Панель управления теперь пустая, настройки перенесены в панель настроек графиков
        # Растягивающий элемент
        layout.addStretch()

        return panel

    def add_channel(self, channel_data: ChannelData):
        """
        Добавить канал для отображения

        Args:
            channel_data: Данные канала
        """
        channel_name = channel_data.name

        if channel_name in self.channels_list:
            self.logger.warning(f"Канал {channel_name} уже добавлен")
            return

        self.channels_list.append(channel_name)

        # Добавляем в контейнер графиков
        self.plot_container.add_channel_to_plot(channel_data)

        # Запрашиваем данные канала
        self.channel_requested.emit(channel_name)

        self.logger.info(f"Канал {channel_name} добавлен в окно графиков")

    def remove_channel(self, channel_name: str):
        """
        Удалить канал из отображения

        Args:
            channel_name: Имя канала
        """
        if channel_name not in self.channels_list:
            return

        self.channels_list.remove(channel_name)

        # Удаляем из контейнера
        self.plot_container.remove_channel(channel_name)

        self.logger.info(f"Канал {channel_name} удален из окна графиков")

    def update_channel_data(self, channel_name: str, channel_data: ChannelData):
        """
        Обновить данные канала

        Args:
            channel_name: Имя канала
            channel_data: Новые данные канала
        """
        if channel_name not in self.channels_list:
            return

        self.plot_container.update_channel_data(channel_name, channel_data)

    def clear_all_channels(self):
        """Очистить все каналы"""
        self.channels_list.clear()
        self.plot_container.clear_all()
        self.logger.info("Все каналы очищены из окна графиков")

    def set_channels_list(self, channels_list: list):
        """
        Установить список каналов для отображения

        Args:
            channels_list: Список имен каналов
        """
        # Очищаем текущие каналы
        self.clear_all_channels()

        # Добавляем новые каналы
        self.channels_list = channels_list.copy()

        # Запрашиваем данные для всех каналов
        for channel_name in self.channels_list:
            self.channel_requested.emit(channel_name)

        self.logger.info(f"Установлен список каналов: {len(channels_list)} каналов")

    def get_channels_list(self) -> list:
        """
        Получить список отображаемых каналов

        Returns:
            Список имен каналов
        """
        return self.channels_list.copy()

    def show_context_menu(self, pos: QPoint):
        """Показать контекстное меню"""
        menu = QMenu(self)

        # Меню для графиков
        add_plot_action = QAction("Добавить график", self)
        add_plot_action.triggered.connect(self._add_new_plot)
        menu.addAction(add_plot_action)

        if self.plot_container.get_plot_count() > 1:
            remove_plot_action = QAction("Удалить график", self)
            remove_plot_action.triggered.connect(self._remove_last_plot)
            menu.addAction(remove_plot_action)

        menu.addSeparator()

        # Меню ориентации
        orientation_menu = menu.addMenu("Ориентация")

        vertical_action = QAction("Вертикальная", self)
        vertical_action.triggered.connect(lambda: self.plot_container.set_layout_orientation(Qt.Vertical))
        orientation_menu.addAction(vertical_action)

        horizontal_action = QAction("Горизонтальная", self)
        horizontal_action.triggered.connect(lambda: self.plot_container.set_layout_orientation(Qt.Horizontal))
        orientation_menu.addAction(horizontal_action)

        menu.addSeparator()

        # Панель управления
        toggle_panel_action = QAction("Скрыть панель управления" if self.control_panel.isVisible() else "Показать панель управления", self)
        toggle_panel_action.triggered.connect(self.toggle_control_panel)
        menu.addAction(toggle_panel_action)

        menu.addSeparator()

        # Очистка
        clear_action = QAction("Очистить все", self)
        clear_action.triggered.connect(self.clear_all_channels)
        menu.addAction(clear_action)

        menu.exec_(self.mapToGlobal(pos))

    def _add_new_plot(self):
        """Добавить новый график"""
        self.plot_container.add_plot()

    def _remove_last_plot(self):
        """Удалить последний график"""
        plots = self.plot_container.plot_widgets
        if len(plots) > 1:
            self.plot_container.remove_plot(plots[-1])

    def _on_channel_moved(self, channel_name: str, from_plot, to_plot):
        """
        Обработчик перемещения канала между графиками

        Args:
            channel_name: Имя канала
            from_plot: Исходный график
            to_plot: Целевой график
        """
        self.logger.debug(f"Канал {channel_name} перемещен между графиками")

    def _on_plot_added(self, plot_widget):
        """
        Обработчик добавления графика

        Args:
            plot_widget: Добавленный график
        """
        self.logger.debug("Добавлен новый график")

    def _on_plot_removed(self, plot_widget):
        """
        Обработчик удаления графика

        Args:
            plot_widget: Удаленный график
        """
        self.logger.debug("Удален график")

    def _on_plot_settings_changed(self):
        """
        Обработчик изменения настроек графика
        """
        self.logger.debug("Настройки графика изменены")
        self.settings_changed.emit()

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Сохраняем конфигурацию
        self.save_config()

        # Удаляем конфигурацию из памяти
        self.window_config.delete_window_config(self.window_id)

        # Отправляем сигнал о закрытии
        self.window_closed.emit()

        # Очищаем каналы
        self.clear_all_channels()

        super().closeEvent(event)

    def get_plot_container(self) -> PlotContainer:
        """
        Получить контейнер графиков

        Returns:
            PlotContainer
        """
        return self.plot_container

    def set_time_window(self, seconds: int):
        """
        Установить окно времени для всех графиков

        Args:
            seconds: Окно времени в секундах
        """
        for plot_widget in self.plot_container.plot_widgets:
            plot_widget.set_time_window(seconds)

    def toggle_control_panel(self):
        """Переключить видимость панели управления"""
        self.control_panel.setVisible(not self.control_panel.isVisible())

    def get_channel_info(self, channel_name: str) -> dict:
        """
        Получить информацию о канале

        Args:
            channel_name: Имя канала

        Returns:
            Словарь с информацией о канале или пустой словарь
        """
        plot_widget = self.plot_container.get_plot_for_channel(channel_name)
        if plot_widget and channel_name in plot_widget.channels:
            channel_data = plot_widget.channels[channel_name]
            return {
                'name': channel_data.name,
                'description': channel_data.description,
                'units': channel_data.units,
                'data_points': len(channel_data),
                'color': channel_data.display_settings['color'],
                'visible': channel_data.display_settings['visible']
            }
        return {}

    def export_plot_data(self, channel_name: str) -> dict:
        """
        Экспортировать данные графика для канала

        Args:
            channel_name: Имя канала

        Returns:
            Словарь с данными графика
        """
        plot_widget = self.plot_container.get_plot_for_channel(channel_name)
        if plot_widget and channel_name in plot_widget.channels:
            channel_data = plot_widget.channels[channel_name]
            timestamps, values = channel_data.get_data_arrays()

            return {
                'channel_name': channel_name,
                'description': channel_data.description,
                'units': channel_data.units,
                'timestamps': timestamps.tolist() if len(timestamps) > 0 else [],
                'values': values.tolist() if len(values) > 0 else [],
                'color': channel_data.display_settings['color']
            }
        return {}

    def save_config(self):
        """
        Сохранить текущую конфигурацию окна
        """
        try:
            # Собираем текущую конфигурацию
            self.current_config.geometry = self.geometry()
            self.current_config.visible_channels = self.channels_list.copy()
            self.current_config.layout_orientation = self.plot_container.layout_orientation
            self.current_config.splitter_sizes = self.plot_container.get_splitter_sizes()

            # Собираем настройки графиков
            self.current_config.plot_settings.clear()
            for plot_widget in self.plot_container.plot_widgets:
                # Сохраняем настройки для каждого канала на графике
                for channel_name in plot_widget.channels.keys():
                    # Используем текущие настройки графика для всех каналов
                    self.current_config.plot_settings[channel_name] = plot_widget.plot_settings

            # Сохраняем
            self.window_config.save_window_config(self.window_id, self.current_config)

            self.logger.info(f"Конфигурация окна {self.window_id} сохранена")

        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации окна {self.window_id}: {e}")

    def load_config(self):
        """
        Загрузить конфигурацию окна
        """
        try:
            config = self.window_config.load_window_config(self.window_id)
            if config is None:
                self.logger.debug(f"Конфигурация для окна {self.window_id} не найдена")
                return

            self.current_config = config

            # Восстанавливаем геометрию
            if config.geometry:
                self.setGeometry(config.geometry)

            # Восстанавливаем ориентацию layout
            self.plot_container.set_layout_orientation(config.layout_orientation)

            # Восстанавливаем размеры сплиттера
            if config.splitter_sizes:
                self.plot_container.set_splitter_sizes(config.splitter_sizes)

            # Восстанавливаем видимые каналы
            if config.visible_channels:
                self.set_channels_list(config.visible_channels)

            # Применяем настройки графиков
            for plot_widget in self.plot_container.plot_widgets:
                for channel_name, settings in config.plot_settings.items():
                    if channel_name in plot_widget.channels:
                        plot_widget.settings_panel.apply_settings(settings)
                        plot_widget.apply_plot_settings(settings)

            self.logger.info(f"Конфигурация окна {self.window_id} загружена")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации окна {self.window_id}: {e}")
