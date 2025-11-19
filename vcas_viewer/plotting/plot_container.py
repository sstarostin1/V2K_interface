# -*- coding: utf-8 -*-
"""
PlotContainer - контейнер для размещения нескольких графиков с поддержкой drag-and-drop
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
import logging
from typing import List, Dict, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from vcas_viewer.plotting.draggable_plot_widget import DraggablePlotWidget
from vcas_viewer.models.channel_data import ChannelData


class PlotContainer(QWidget):
    """
    Контейнер для размещения нескольких графиков с поддержкой drag-and-drop
    между графиками и управления компоновкой
    """

    # Сигналы
    channel_moved = pyqtSignal(str, object, object)  # channel_name, from_widget, to_widget
    plot_added = pyqtSignal(object)  # new_plot_widget
    plot_removed = pyqtSignal(object)  # removed_plot_widget

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('PlotContainer')

        # Список графиков
        self.plot_widgets: List[DraggablePlotWidget] = []

        # Карта каналов: channel_name -> plot_widget
        self.channel_map: Dict[str, DraggablePlotWidget] = {}

        # Настройки
        self.max_plots = 6  # Максимальное количество графиков
        self.default_plot_title = "График"
        self.layout_orientation = Qt.Vertical  # Ориентация layout

        self.setup_ui()
        self.setup_connections()

        # Создаем начальный график
        self.add_plot()

    def setup_ui(self):
        """Настройка интерфейса"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Создаем splitter для разделения графиков
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.main_layout.addWidget(self.splitter)

    def setup_connections(self):
        """Настройка соединений сигналов"""
        # Сигналы будут настраиваться при добавлении графиков
        pass

    def add_plot(self) -> DraggablePlotWidget:
        """
        Добавить новый график

        Returns:
            Созданный виджет графика
        """
        if len(self.plot_widgets) >= self.max_plots:
            self.logger.warning(f"Достигнуто максимальное количество графиков: {self.max_plots}")
            return None

        # Создаем новый график
        plot_widget = DraggablePlotWidget()
        plot_widget.setMinimumHeight(200)

        # Добавляем в splitter
        self.splitter.addWidget(plot_widget)
        self.plot_widgets.append(plot_widget)

        # Настраиваем соединения сигналов
        self._connect_plot_signals(plot_widget)

        # Обновляем заголовки
        self._update_plot_titles()

        # Отправляем сигнал
        self.plot_added.emit(plot_widget)

        self.logger.info(f"Добавлен новый график. Всего графиков: {len(self.plot_widgets)}")

        return plot_widget

    def remove_plot(self, plot_widget: DraggablePlotWidget):
        """
        Удалить график

        Args:
            plot_widget: Виджет графика для удаления
        """
        if plot_widget not in self.plot_widgets:
            return

        if len(self.plot_widgets) <= 1:
            self.logger.warning("Нельзя удалить последний график")
            return

        # Отключаем сигналы
        self._disconnect_plot_signals(plot_widget)

        # Перемещаем каналы с удаляемого графика на другие
        channels_to_move = plot_widget.get_channel_names()
        for channel_name in channels_to_move:
            # Находим другой график для перемещения
            target_plot = None
            for pw in self.plot_widgets:
                if pw != plot_widget and not pw.has_channel(channel_name):
                    target_plot = pw
                    break

            if target_plot:
                self.move_channel_to_plot(channel_name, plot_widget, target_plot)
            else:
                # Если не нашли куда переместить, просто удаляем
                self.logger.warning(f"Канал {channel_name} удален при удалении графика")

        # Удаляем из splitter и списка
        self.splitter.widget(self.plot_widgets.index(plot_widget)).setParent(None)
        self.plot_widgets.remove(plot_widget)

        # Обновляем заголовки
        self._update_plot_titles()

        # Отправляем сигнал
        self.plot_removed.emit(plot_widget)

        self.logger.info(f"График удален. Осталось графиков: {len(self.plot_widgets)}")

    def move_channel_to_plot(self, channel_name: str, from_plot: DraggablePlotWidget,
                           to_plot: DraggablePlotWidget):
        """
        Переместить канал с одного графика на другой

        Args:
            channel_name: Имя канала
            from_plot: Исходный график
            to_plot: Целевой график
        """
        if channel_name not in self.channel_map:
            self.logger.warning(f"Канал {channel_name} не найден в карте каналов")
            return

        if self.channel_map[channel_name] != from_plot:
            self.logger.warning(f"Канал {channel_name} не принадлежит исходному графику")
            return

        if to_plot.has_channel(channel_name):
            self.logger.warning(f"Канал {channel_name} уже присутствует на целевом графике")
            return

        # Получаем данные канала
        channel_data = None
        for ch_name, ch_data in from_plot.channels.items():
            if ch_name == channel_name:
                channel_data = ch_data
                break

        if not channel_data:
            self.logger.error(f"Не удалось получить данные канала {channel_name}")
            return

        # Удаляем канал с исходного графика
        from_plot.remove_channel(channel_name)

        # Добавляем на целевой график
        to_plot.add_channel(channel_data)

        # Обновляем карту каналов
        self.channel_map[channel_name] = to_plot

        # Отправляем сигнал
        self.channel_moved.emit(channel_name, from_plot, to_plot)

        self.logger.info(f"Канал {channel_name} перемещен с графика {id(from_plot)} на график {id(to_plot)}")

    def add_channel_to_plot(self, channel_data: ChannelData, plot_widget: Optional[DraggablePlotWidget] = None):
        """
        Добавить канал на указанный график (или на первый доступный)

        Args:
            channel_data: Данные канала
            plot_widget: Целевой график (None для автоматического выбора)
        """
        channel_name = channel_data.name

        # Проверяем, не добавлен ли уже канал
        if channel_name in self.channel_map:
            self.logger.warning(f"Канал {channel_name} уже присутствует в контейнере")
            return

        # Выбираем график
        if plot_widget is None:
            # Автоматический выбор - добавляем на график с наименьшим количеством каналов
            plot_widget = min(self.plot_widgets, key=lambda pw: len(pw.channels))

        # Добавляем канал
        plot_widget.add_channel(channel_data)
        self.channel_map[channel_name] = plot_widget

        self.logger.info(f"Канал {channel_name} добавлен на график {id(plot_widget)}")

    def remove_channel(self, channel_name: str):
        """
        Удалить канал из контейнера

        Args:
            channel_name: Имя канала
        """
        if channel_name not in self.channel_map:
            return

        plot_widget = self.channel_map[channel_name]
        plot_widget.remove_channel(channel_name)
        del self.channel_map[channel_name]

        self.logger.info(f"Канал {channel_name} удален из контейнера")

    def update_channel_data(self, channel_name: str, channel_data: ChannelData):
        """
        Обновить данные канала

        Args:
            channel_name: Имя канала
            channel_data: Новые данные канала
        """
        if channel_name not in self.channel_map:
            self.logger.warning(f"Канал {channel_name} не найден в контейнере")
            return

        plot_widget = self.channel_map[channel_name]
        plot_widget.update_channel_data(channel_name, channel_data)

    def get_plot_for_channel(self, channel_name: str) -> Optional[DraggablePlotWidget]:
        """
        Получить график, на котором находится канал

        Args:
            channel_name: Имя канала

        Returns:
            Виджет графика или None
        """
        return self.channel_map.get(channel_name)

    def get_all_channels(self) -> Dict[str, DraggablePlotWidget]:
        """
        Получить все каналы и их графики

        Returns:
            Словарь channel_name -> plot_widget
        """
        return self.channel_map.copy()

    def clear_all(self):
        """Очистить все графики"""
        for plot_widget in self.plot_widgets:
            plot_widget.clear()

        self.channel_map.clear()
        self.logger.info("Все графики очищены")

    def _connect_plot_signals(self, plot_widget: DraggablePlotWidget):
        """
        Подключить сигналы графика

        Args:
            plot_widget: Виджет графика
        """
        plot_widget.channel_dropped.connect(self._on_channel_dropped)
        plot_widget.channel_dragged.connect(self._on_channel_dragged)
        plot_widget.channel_removed.connect(self._on_channel_removed)

    def _disconnect_plot_signals(self, plot_widget: DraggablePlotWidget):
        """
        Отключить сигналы графика

        Args:
            plot_widget: Виджет графика
        """
        plot_widget.channel_dropped.disconnect(self._on_channel_dropped)
        plot_widget.channel_dragged.disconnect(self._on_channel_dragged)
        plot_widget.channel_removed.disconnect(self._on_channel_removed)

    def _on_channel_dropped(self, channel_name: str, target_widget: DraggablePlotWidget):
        """
        Обработчик сброса канала на график

        Args:
            channel_name: Имя канала
            target_widget: Целевой график
        """
        # Находим исходный график
        source_widget = self.channel_map.get(channel_name)

        if source_widget and source_widget != target_widget:
            # Перемещаем канал
            self.move_channel_to_plot(channel_name, source_widget, target_widget)

    def _on_channel_dragged(self, channel_name: str, source_widget: DraggablePlotWidget):
        """
        Обработчик начала перетаскивания канала

        Args:
            channel_name: Имя канала
            source_widget: Исходный график
        """
        self.logger.debug(f"Начато перетаскивание канала {channel_name} с графика {id(source_widget)}")

    def _on_channel_removed(self, channel_name: str):
        """
        Обработчик удаления канала из графика

        Args:
            channel_name: Имя канала
        """
        # Удаляем из карты каналов
        if channel_name in self.channel_map:
            del self.channel_map[channel_name]

        self.logger.debug(f"Канал {channel_name} удален из карты каналов")

    def _update_plot_titles(self):
        """Обновить заголовки всех графиков"""
        for i, plot_widget in enumerate(self.plot_widgets):
            if len(self.plot_widgets) == 1:
                plot_widget.title_label.setText(self.default_plot_title)
            else:
                plot_widget.title_label.setText(f"{self.default_plot_title} {i + 1}")

    def set_layout_orientation(self, orientation: Qt.Orientation):
        """
        Установить ориентацию компоновки графиков

        Args:
            orientation: Qt.Vertical или Qt.Horizontal
        """
        self.splitter.setOrientation(orientation)
        self.logger.info(f"Ориентация компоновки изменена на {orientation}")

    def split_plot(self, plot_widget: DraggablePlotWidget):
        """
        Разделить график на два

        Args:
            plot_widget: График для разделения
        """
        if len(self.plot_widgets) >= self.max_plots:
            self.logger.warning("Достигнуто максимальное количество графиков")
            return

        # Создаем новый график
        new_plot = self.add_plot()

        # Перемещаем половину каналов на новый график
        channels = list(plot_widget.channels.keys())
        half_count = len(channels) // 2

        for i in range(half_count):
            channel_name = channels[i]
            self.move_channel_to_plot(channel_name, plot_widget, new_plot)

        self.logger.info(f"График разделен. Каналы перемещены: {half_count}")

    def get_plot_count(self) -> int:
        """
        Получить количество графиков

        Returns:
            Количество графиков
        """
        return len(self.plot_widgets)

    def get_channel_count(self) -> int:
        """
        Получить общее количество каналов

        Returns:
            Количество каналов
        """
        return len(self.channel_map)

    def get_splitter_sizes(self) -> List[int]:
        """
        Получить размеры областей сплиттера

        Returns:
            Список размеров
        """
        return self.splitter.sizes()

    def set_splitter_sizes(self, sizes: List[int]):
        """
        Установить размеры областей сплиттера

        Args:
            sizes: Список размеров
        """
        if sizes and len(sizes) == len(self.plot_widgets):
            self.splitter.setSizes(sizes)
            self.logger.debug(f"Размеры сплиттера установлены: {sizes}")
