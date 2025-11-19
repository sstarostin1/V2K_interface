# -*- coding: utf-8 -*-
"""
DraggablePlotWidget - виджет графика с поддержкой drag-and-drop для перемещения кривых
"""

import pyqtgraph as pg
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMenu, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QTimer
from PyQt5.QtGui import QDrag, QPixmap, QPainter, QColor, QIcon
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from collections import deque
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from vcas_viewer.models.channel_data import ChannelData
from vcas_viewer.plotting.plot_settings_panel import PlotSettingsPanel, PlotSettings, FillMode


class DraggablePlotWidget(QWidget):
    """
    Виджет графика с поддержкой drag-and-drop для перемещения кривых между графиками
    """

    # Сигналы
    channel_dropped = pyqtSignal(str, object)  # channel_name, target_widget
    channel_dragged = pyqtSignal(str, object)  # channel_name, source_widget
    channel_removed = pyqtSignal(str)  # channel_name
    settings_changed = pyqtSignal()  # Настройки графика изменены

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('DraggablePlotWidget')

        # Данные каналов: channel_name -> ChannelData
        self.channels: Dict[str, ChannelData] = {}

        # Кривые на графике: channel_name -> PlotDataItem
        self.plot_curves: Dict[str, pg.PlotDataItem] = {}

        # Цвета для каналов
        self.channel_colors = [
            '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF',
            '#800000', '#008000', '#000080', '#808000', '#800080', '#008080'
        ]

        # Настройки графика
        self.time_window = 300  # секунды (5 минут по умолчанию)
        self.max_points = 1000  # максимальное количество точек на канал

        # Режим заполнения графика
        self.fill_mode = FillMode.ROLLING_RIGHT

        # Таймер для сканирующего режима
        self.sweep_timer = QTimer()
        self.sweep_timer.timeout.connect(self._update_sweeping_range)

        # Переменные для истинного сканирующего режима
        self.sweep_start_time = 0.0  # Начало текущего цикла сканирования
        self.sweep_y_ranges = deque(maxlen=5)  # История диапазонов Y для стабилизации масштаба

        # Кэш удаляемых данных: channel_name -> [(timestamp, value), ...]
        # Сохраняется до закрытия окна для возможного восстановления
        self.cached_old_data: Dict[str, List[Tuple[float, float]]] = {}

        # Настройки графика
        self.plot_settings = PlotSettings()

        # Панель настроек
        self.settings_panel = None
        self.settings_button = None

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок графика с кнопкой настроек
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(5, 5, 5, 5)

        self.title_label = QLabel("График")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold;")
        title_layout.addWidget(self.title_label)

        # Кнопка настроек
        self.settings_button = QPushButton()
        self.settings_button.setFixedSize(20, 20)
        self.settings_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        self.settings_button.setText("⚙")
        self.settings_button.clicked.connect(self.show_settings_panel)
        title_layout.addWidget(self.settings_button)

        layout.addLayout(title_layout)

        # График pyqtgraph
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)

        # Настройка осей
        self.plot_widget.setLabel('left', 'Значение')
        self.plot_widget.setLabel('bottom', 'Время')

        # Использовать DateAxisItem для красивого отображения времени
        from pyqtgraph import DateAxisItem
        date_axis = DateAxisItem(orientation='bottom', format='%H:%M:%S')  # Используем системную локальную timezone (Bangkok UTC+7)
        self.plot_widget.setAxisItems({'bottom': date_axis})

        # Включаем drag-and-drop
        self.plot_widget.setAcceptDrops(True)
        self.setAcceptDrops(True)

        layout.addWidget(self.plot_widget)

        # Создаем панель настроек
        self.settings_panel = PlotSettingsPanel(self)
        self.settings_panel.settings_changed.connect(self._on_settings_changed)

        # Настройка контекстного меню
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self.show_context_menu)

    def setup_connections(self):
        """Настройка соединений сигналов"""
        # Обработка drag-and-drop событий
        self.plot_widget.dragEnterEvent = self.drag_enter_event
        self.plot_widget.dragMoveEvent = self.drag_move_event
        self.plot_widget.dropEvent = self.drop_event

    def add_channel(self, channel_data: ChannelData):
        """
        Добавить канал на график

        Args:
            channel_data: Данные канала
        """
        channel_name = channel_data.name

        if channel_name in self.channels:
            self.logger.warning(f"Канал {channel_name} уже присутствует на графике")
            return

        # Сохраняем данные канала
        self.channels[channel_name] = channel_data

        # Назначаем цвет если не назначен
        if channel_data.display_settings['color'] is None:
            color_index = len(self.channels) % len(self.channel_colors)
            channel_data.set_display_color(self.channel_colors[color_index])

        # Создаем кривую на графике
        self._create_plot_curve(channel_name)

        # Обновляем заголовок
        self._update_title()

        self.logger.info(f"Канал {channel_name} добавлен на график")

    def remove_channel(self, channel_name: str):
        """
        Удалить канал с графика

        Args:
            channel_name: Имя канала
        """
        if channel_name not in self.channels:
            return

        # Удаляем кривую с графика
        if channel_name in self.plot_curves:
            curve = self.plot_curves[channel_name]
            self.plot_widget.removeItem(curve)
            del self.plot_curves[channel_name]

        # Удаляем данные канала
        del self.channels[channel_name]

        # Очищаем кэш удаляемых данных для этого канала
        if channel_name in self.cached_old_data:
            count = len(self.cached_old_data[channel_name])
            del self.cached_old_data[channel_name]
            self.logger.debug(f"Очищен кэш старых данных канала {channel_name}: удалено {count} точек")

        # Обновляем заголовок
        self._update_title()

        # Отправляем сигнал
        self.channel_removed.emit(channel_name)

        self.logger.info(f"Канал {channel_name} удален с графика")

    def update_channel_data(self, channel_name: str, channel_data: ChannelData):
        """
        Обновить данные канала

        Args:
            channel_name: Имя канала
            channel_data: Новые данные канала
        """
        if channel_name not in self.channels:
            self.logger.warning(f"Попытка обновить данные несуществующего канала {channel_name}")
            return

        # Обновляем данные
        self.channels[channel_name] = channel_data

        # Ограничиваем количество точек
        channel_data.limit_data_points(self.max_points)

        # Обновляем кривую
        self._update_plot_curve(channel_name)

        # Фиксированное окно в сканирующем режиме - сдвиг не нужен

        # Обновляем масштаб времени для отражения новых данных
        self._update_time_range()

        # В сканирующем режиме адаптивно обновляем вертикальный масштаб
        if self.fill_mode == FillMode.SWEEPING_LEFT:
            self._update_y_range_adaptively()

    def _create_plot_curve(self, channel_name: str):
        """
        Создать кривую на графике для канала

        Args:
            channel_name: Имя канала
        """
        if channel_name not in self.channels:
            return

        channel_data = self.channels[channel_name]
        color = channel_data.display_settings['color']

        # Получаем данные
        timestamps, values = channel_data.get_data_arrays()

        if len(timestamps) == 0:
            # Создаем пустую кривую
            curve = self.plot_widget.plot([], [],
                                        pen=pg.mkPen(color=color, width=2),
                                        name=channel_name,
                                        symbol='o', symbolSize=4, symbolBrush=color)
        else:
            # Создаем кривую с данными
            curve = self.plot_widget.plot(timestamps, values,
                                        pen=pg.mkPen(color=color, width=2),
                                        name=channel_name,
                                        symbol='o', symbolSize=4, symbolBrush=color)

        self.plot_curves[channel_name] = curve

        # Добавляем легенду если несколько каналов
        if len(self.plot_curves) > 1:
            self._update_legend()

    def _update_plot_curve(self, channel_name: str):
        """
        Обновить кривую на графике

        Args:
            channel_name: Имя канала
        """
        if channel_name not in self.plot_curves:
            return

        channel_data = self.channels[channel_name]
        curve = self.plot_curves[channel_name]

        # Получаем данные
        timestamps, values = channel_data.get_data_arrays()

        # Обновляем данные кривой
        curve.setData(timestamps, values)

    def _update_legend(self):
        """Обновить легенду графика"""
        # Удаляем существующую легенду
        plot_item = self.plot_widget.getPlotItem()
        if plot_item.legend is not None:
            plot_item.legend.scene().removeItem(plot_item.legend)
            plot_item.legend = None

        # Создаем новую легенду
        legend = self.plot_widget.addLegend()

        # Добавляем все кривые в легенду
        for channel_name, curve in self.plot_curves.items():
            legend.addItem(curve, channel_name)

    def _update_title(self):
        """Обновить заголовок графика"""
        if not self.channels:
            self.title_label.setText("График (пустой)")
        elif len(self.channels) == 1:
            channel_name = list(self.channels.keys())[0]
            self.title_label.setText(f"График: {channel_name}")
        else:
            self.title_label.setText(f"График ({len(self.channels)} каналов)")

    def set_time_window(self, seconds: int):
        """
        Установить окно времени для отображения

        Args:
            seconds: Окно времени в секундах
        """
        self.time_window = seconds
        self._update_time_range()

    def get_time_window(self) -> int:
        """
        Получить текущее окно времени

        Returns:
            Окно времени в секундах
        """
        return self.time_window

    def _update_time_range(self):
        """Обновить диапазон времени на графике в зависимости от режима"""
        if self.fill_mode == FillMode.SWEEPING_LEFT:
            self._update_sweeping_range()
        else:  # FillMode.ROLLING_RIGHT
            self._update_rolling_range()

    def _update_rolling_range(self):
        """Обновить диапазон для скользящего режима (скользит за текущим временем)"""
        if not self.channels:
            return

        # Находим самое позднее время (current_time) - конец данных
        current_time = float('-inf')
        for channel_data in self.channels.values():
            _, ch_max = channel_data.get_time_range()
            if ch_max is not None:
                current_time = max(current_time, ch_max)

        if current_time != float('-inf'):
            # Вычисляем скользящее окно: от current_time - time_window до current_time
            window_start = current_time - self.time_window
            self.plot_widget.setXRange(window_start, current_time, padding=0.01)

            self.logger.debug(f"Скользящее окно: [{window_start:.1f}, {current_time:.1f}] (ширина: {self.time_window}с)")

            # Очистка старых данных за пределами разумного лимита
            # (сохраняем данные за пределами экрана, но ограничиваем память)
            self._cleanup_old_data_beyond_limit(current_time - self.time_window * 2)

    def _update_sweeping_range(self):
        """Обновить диапазон для сканирующего слева режима с накоплением от левого края (ограниченная ширина time_window)"""
        if not self.channels:
            return

        # Находим самое позднее время (current_time)
        current_time = float('-inf')
        for channel_data in self.channels.values():
            _, ch_max = channel_data.get_time_range()
            if ch_max is not None:
                current_time = max(current_time, ch_max)

        if current_time != float('-inf'):
            # Логика накопления: фиксированное окно шириной time_window от sweep_start_time
            window_start = self.sweep_start_time
            window_end = self.sweep_start_time + self.time_window

            # Устанавливаем окно
            self.plot_widget.setXRange(window_start, window_end, padding=0.01)

            self.logger.debug(f"Фиксированное сканирующее окно: [{window_start:.1f}, {window_end:.1f}] (ширина: {self.time_window}с)")

            # Захватываем диапазон Y для стабильности (накапливаем историю последних измерений)
            self._capture_current_y_range()

            # Применяем адаптивный Y-диапазон на основе истории
            self._update_y_range_adaptively(save_to_history=False)

            # Очистка старых данных за пределами критической дистанции (5 * time_window, с кэшированием)
            self._cleanup_old_data_beyond_limit(window_start - 4 * self.time_window)
        else:
            self.logger.debug("Нет данных для сканирующего режима")

    def _cleanup_old_data(self, window_start: float):
        """
        Очистить старые данные за пределами окна в сканирующем режиме

        Args:
            window_start: Начало временного окна
        """
        for channel_name, channel_data in self.channels.items():
            # Получаем текущие данные
            timestamps, values = channel_data.get_data_arrays()

            if len(timestamps) == 0:
                continue

            # Находим индексы данных, которые находятся в окне
            import numpy as np
            timestamps_array = np.array(timestamps)
            valid_indices = timestamps_array >= window_start

            # Если есть данные за пределами окна
            if not np.all(valid_indices):
                # Оставляем только данные в окне
                filtered_timestamps = timestamps_array[valid_indices]
                filtered_values = np.array(values)[valid_indices]

                # Обновляем данные канала
                channel_data.clear_data()
                if len(filtered_timestamps) > 0:
                    channel_data.add_data_points(filtered_timestamps.tolist(), filtered_values.tolist(), use_system_time=False)

                # Если данные изменились, обновляем кривую
                if not np.all(valid_indices):
                    self._update_plot_curve(channel_name)
                    self.logger.debug(f"Очищены старые данные канала {channel_name}: осталось {len(filtered_timestamps)} точек")

    def _cleanup_old_data_beyond_limit(self, limit_time: float):
        """
        Очистить очень старые данные за пределами разумного лимита (для скользящего режима)
        Удаляемые данные сохраняются в кэш до закрытия окна графика для возможного восстановления

        Args:
            limit_time: Время, раньше которого удаляем данные
        """
        # Для скользящего режима сохраняем данные и слева и справа от видимого окна
        # но ограничиваем память, удаляя слишком старые данные с кэшированием
        for channel_name, channel_data in self.channels.items():
            timestamps, values = channel_data.get_data_arrays()

            if len(timestamps) == 0:
                continue

            # Находим индексы данных, которые НУЖНО сохранить (не старше limit_time)
            timestamps_array = np.array(timestamps)
            keep_indices = timestamps_array >= limit_time

            # Если есть данные для удаления
            if not np.all(keep_indices):
                # Инициализируем кэш для канала, если нужно
                if channel_name not in self.cached_old_data:
                    self.cached_old_data[channel_name] = []

                # Выделяем удаляемые данные и добавляем в кэш
                remove_indices = ~keep_indices
                removed_timestamps = timestamps_array[remove_indices]
                removed_values = np.array(values)[remove_indices]

                # Добавляем каждую точку в кэш
                for ts, val in zip(removed_timestamps, removed_values):
                    self.cached_old_data[channel_name].append((float(ts), float(val)))

                self.logger.debug(f"Закэшированы старые данные канала {channel_name}: добавлено {len(removed_timestamps)} точек в кэш")

                # Оставляем только новые данные
                filtered_timestamps = timestamps_array[keep_indices]
                filtered_values = np.array(values)[keep_indices]

                # Очищаем и записываем обратно
                channel_data.clear_data()
                if len(filtered_timestamps) > 0:
                    channel_data.add_data_points(filtered_timestamps.tolist(), filtered_values.tolist(), use_system_time=False)

                # Обновляем кривую (только если данные реально изменились)
                if len(filtered_timestamps) < len(timestamps):
                    self._update_plot_curve(channel_name)
                    removed_count = len(timestamps) - len(filtered_timestamps)
                    cached_count = len(self.cached_old_data[channel_name])
                    self.logger.debug(f"Удалены старые данные канала {channel_name}: удалено {removed_count} точек, осталось {len(filtered_timestamps)}, в кэше {cached_count}")

    def _capture_current_y_range(self):
        """
        Сохранить текущий диапазон вертикальной оси перед очисткой графика
        """
        if not self.channels:
            return

        current_min = float('inf')
        current_max = float('-inf')

        for channel_data in self.channels.values():
            ch_min, ch_max = channel_data.get_value_range()
            if ch_min is not None and ch_max is not None:
                current_min = min(current_min, ch_min)
                current_max = max(current_max, ch_max)

        if current_min != float('inf'):
            self.sweep_y_ranges.append((current_min, current_max))
            self.logger.debug(f"Сохранён Y-диапазон: [{current_min:.2f}, {current_max:.2f}], история: {len(self.sweep_y_ranges)}")

    def _update_y_range_adaptively(self, save_to_history=False):
        """
        Адаптивное обновление вертикального масштаба графика

        Коррелирует минимальный диапазон из истории с текущими данными, позволяя расширение вверх

        Args:
            save_to_history: Если True, сохранить текущий диапазон в историю (при очистке)
        """
        if not self.channels:
            return

        # Шаг 1: Рассчитываем текущий диапазон данных всех каналов
        current_min = float('inf')
        current_max = float('-inf')

        for channel_data in self.channels.values():
            ch_min, ch_max = channel_data.get_value_range()
            if ch_min is not None and ch_max is not None:
                current_min = min(current_min, ch_min)
                current_max = max(current_max, ch_max)

        if current_min == float('inf'):
            # Нет данных для масштаба
            self.logger.debug("Нет данных каналов для масштабирования Y")
            return

        # Шаг 2: Определяем стабильный диапазон на основе истории + текущих данных
        if self.sweep_y_ranges:
            # Используем историю как нижнюю границу
            history_min = min(min_y for min_y, _ in self.sweep_y_ranges)
            history_max = max(max_y for _, max_y in self.sweep_y_ranges)

            # Комбинируем: минимум из истории и текущих, максимум расширяется динамически
            stable_min = min(history_min, current_min)
            stable_max = max(history_max, current_max)
        else:
            # Нет истории: используем только текущие данные
            stable_min = current_min
            stable_max = current_max

        # Шаг 3: Добавляем padding для лучшей видимости
        range_width = stable_max - stable_min
        padding = range_width * 0.05 if range_width > 0 else 1.0

        # Шаг 4: Применяем диапазон к графику
        self.plot_widget.setYRange(stable_min - padding, stable_max + padding)

        # Шаг 5: Сохраняем в историю при очистке графика
        if save_to_history:
            self.sweep_y_ranges.append((stable_min, stable_max))
            self.logger.debug(f"Сохранён расширенный Y-диапазон в истории: [{stable_min:.2f}, {stable_max:.2f}], история: {len(self.sweep_y_ranges)}")

        self.logger.debug(f"Адаптивный Y-диапазон: [{stable_min:.2f}, {stable_max:.2f}] (текущий: [{current_min:.2f}, {current_max:.2f}], история: {len(self.sweep_y_ranges)})")

    def _initialize_sweep_start_time(self):
        """
        Инициализировать начало сканирования слева от текущих данных
        """
        if not self.channels:
            self.sweep_start_time = time.time() - self.time_window
            return

        # Находим самый ранний timestamp среди всех каналов
        earliest_time = float('inf')

        for channel_data in self.channels.values():
            ch_min, _ = channel_data.get_time_range()
            if ch_min is not None:
                earliest_time = min(earliest_time, ch_min)

        if earliest_time == float('inf'):
            # Нет данных - начинаем с текущего времени минус окно
            self.sweep_start_time = time.time() - self.time_window
        else:
            # Начинаем с самых ранних данных (слева)
            self.sweep_start_time = earliest_time

        self.logger.debug(f"Инициализировано начало сканирования: sweep_start_time={self.sweep_start_time:.1f}")

    def clear(self):
        """Очистить график"""
        # Удаляем все кривые
        for curve in self.plot_curves.values():
            self.plot_widget.removeItem(curve)

        self.plot_curves.clear()
        self.channels.clear()

        # Очищаем кэш старых данных при полной очистке графика
        total_cached = sum(len(data_list) for data_list in self.cached_old_data.values())
        if total_cached > 0:
            self.cached_old_data.clear()
            self.logger.debug(f"Очищен кэш старых данных при очистке графика: удалено {total_cached} точек")

        self._update_title()

    # Drag and Drop functionality

    def mousePressEvent(self, event):
        """Обработка нажатия кнопки мыши для начала drag"""
        if event.button() == Qt.LeftButton:
            # Определяем, над какой кривой находится курсор
            pos = event.pos()
            plot_pos = self.plot_widget.mapFrom(self, pos)

            # Проверяем, находится ли курсор над какой-либо кривой
            for channel_name, curve in self.plot_curves.items():
                if self._is_point_on_curve(plot_pos, curve):
                    self._start_drag(channel_name, event.pos())
                    event.accept()
                    return

        super().mousePressEvent(event)

    def _is_point_on_curve(self, plot_pos, curve) -> bool:
        """
        Проверить, находится ли точка над кривой

        Args:
            plot_pos: Позиция в координатах plot_widget
            curve: Кривая графика

        Returns:
            True если точка над кривой
        """
        # Получаем данные кривой
        data = curve.getData()
        if data is None:
            return False

        x_data, y_data = data
        if x_data is None or y_data is None or len(x_data) == 0 or len(y_data) == 0:
            return False

        # Конвертируем позицию курсора в координаты графика
        view_box = self.plot_widget.getViewBox()
        mouse_point = view_box.mapSceneToView(plot_pos)

        # Проверяем близость к точкам кривой (в пределах 10 пикселей)
        tolerance = 10

        for x, y in zip(x_data, y_data):
            point_pos = view_box.mapViewToScene(QPoint(int(x), int(y)))
            distance = (plot_pos - point_pos).manhattanLength()
            if distance <= tolerance:
                return True

        return False

    def _start_drag(self, channel_name: str, pos: QPoint):
        """
        Начать перетаскивание канала

        Args:
            channel_name: Имя канала
            pos: Позиция курсора
        """
        self.logger.info(f"Начато перетаскивание канала {channel_name}")

        # Создаем объект перетаскивания
        drag = QDrag(self)

        # Создаем MIME данные
        mime_data = QMimeData()
        mime_data.setText(f"channel:{channel_name}")
        drag.setMimeData(mime_data)

        # Создаем изображение для перетаскивания
        pixmap = QPixmap(100, 20)
        pixmap.fill(QColor(200, 200, 255, 150))
        painter = QPainter(pixmap)
        painter.drawText(5, 15, channel_name)
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(50, 10))

        # Выполняем перетаскивание
        result = drag.exec_(Qt.MoveAction)

        # Отправляем сигнал о завершении перетаскивания
        self.channel_dragged.emit(channel_name, self)

    def drag_enter_event(self, event):
        """Обработка входа drag объекта"""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("channel:"):
                event.acceptProposedAction()
                return

        event.ignore()

    def drag_move_event(self, event):
        """Обработка движения drag объекта"""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("channel:"):
                event.acceptProposedAction()
                return

        event.ignore()

    def drop_event(self, event):
        """Обработка сброса drag объекта"""
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("channel:"):
                channel_name = text.split(":", 1)[1]
                self.logger.info(f"Канал {channel_name} сброшен на график")

                # Отправляем сигнал о сбросе канала
                self.channel_dropped.emit(channel_name, self)

                event.acceptProposedAction()
                return

        event.ignore()

    def show_context_menu(self, pos):
        """Показать контекстное меню"""
        menu = QMenu(self)

        # Определяем канал под курсором
        plot_pos = self.plot_widget.mapFromGlobal(self.mapToGlobal(pos))
        target_channel = None

        for channel_name, curve in self.plot_curves.items():
            if self._is_point_on_curve(plot_pos, curve):
                target_channel = channel_name
                break

        if target_channel:
            # Меню для конкретного канала
            remove_action = menu.addAction(f"Удалить канал '{target_channel}'")
            remove_action.triggered.connect(lambda: self.remove_channel(target_channel))

            menu.addSeparator()

            # Опции видимости
            channel_data = self.channels[target_channel]
            visible_action = menu.addAction("Скрыть канал" if channel_data.display_settings['visible'] else "Показать канал")
            visible_action.triggered.connect(lambda: self._toggle_channel_visibility(target_channel))

        else:
            # Общее меню
            if self.channels:
                clear_action = menu.addAction("Очистить график")
                clear_action.triggered.connect(self.clear)

        if not menu.isEmpty():
            menu.exec_(self.mapToGlobal(pos))

    def _toggle_channel_visibility(self, channel_name: str):
        """
        Переключить видимость канала

        Args:
            channel_name: Имя канала
        """
        if channel_name in self.channels:
            channel_data = self.channels[channel_name]
            visible = not channel_data.display_settings['visible']
            channel_data.set_visibility(visible)

            curve = self.plot_curves[channel_name]
            curve.setVisible(visible)

            self.logger.info(f"Видимость канала {channel_name} установлена в {visible}")

    def get_channel_names(self) -> List[str]:
        """
        Получить список имен каналов на графике

        Returns:
            Список имен каналов
        """
        return list(self.channels.keys())

    def has_channel(self, channel_name: str) -> bool:
        """
        Проверить, присутствует ли канал на графике

        Args:
            channel_name: Имя канала

        Returns:
            True если канал присутствует
        """
        return channel_name in self.channels

    def resizeEvent(self, event):
        """Обработчик изменения размера виджета"""
        super().resizeEvent(event)

        # Обновляем позицию панели настроек если она открыта
        if self.settings_panel and self.settings_panel.is_visible:
            self.settings_panel.update_panel_position()

    def show_settings_panel(self):
        """
        Показать/скрыть панель настроек графика
        """
        if self.settings_panel:
            self.settings_panel.toggle_panel()

    def _on_settings_changed(self):
        """
        Обработчик изменения настроек панели
        """
        if self.settings_panel:
            settings = self.settings_panel.current_settings
            self.apply_plot_settings(settings)

            # Отправляем сигнал об изменении настроек
            self.settings_changed.emit()

    def apply_plot_settings(self, settings: PlotSettings):
        """
        Применить настройки к графику

        Args:
            settings: Настройки графика
        """
        old_fill_mode = self.fill_mode
        self.plot_settings = settings
        self.fill_mode = settings.fill_mode

        # Применяем настройки времени
        seconds = settings.time_window_minutes * 60
        self.set_time_window(seconds)

        # Для SWEEPING_LEFT режима корректируем позицию окна от последней точки данных
        if self.fill_mode == FillMode.SWEEPING_LEFT:
            # Находим лог last_data_timestamp среди каналов
            current_time = float('-inf')
            for channel_data in self.channels.values():
                _, ch_max = channel_data.get_time_range()
                if ch_max is not None:
                    current_time = max(current_time, ch_max)

            if current_time != float('-inf'):
                self.sweep_start_time = current_time - seconds
                self.logger.debug(f"Обновлено начало сканирования от последней точки: sweep_start_time = {self.sweep_start_time:.1f}")
            else:
                # Если данных нет, используем системное время
                self.sweep_start_time = time.time() - seconds
                self.logger.debug(f"Обновлено начало сканирования от системного времени: sweep_start_time = {self.sweep_start_time:.1f}")

            self._update_time_range()

        # Применяем настройку использования системного времени ко всем каналам
        for channel_data in self.channels.values():
            channel_data.use_system_time = settings.use_system_time

        # Обновляем таймер сканирования в зависимости от режима
        if old_fill_mode != self.fill_mode:
            # При изменении режима очищаем историю диапазонов Y
            self.sweep_y_ranges.clear()
            self.logger.debug("Очищена история диапазонов Y при изменении режима заполнения")

            if self.fill_mode == FillMode.SWEEPING_LEFT:
                # Инициализировать старт сканирования слева
                self._initialize_sweep_start_time()
                # В сканирующем режиме включаем таймер для периодического обновления
                self.sweep_timer.setInterval(1000)  # Каждую секунду
                self.sweep_timer.start()
                self.logger.debug("Таймер сканирования запущен для накопительного режима")
            else:
                # В скользящем режиме останавливаем таймер
                self.sweep_timer.stop()
                self.logger.debug("Таймер сканирования остановлен")

        self.logger.debug(f"Настройки графика применены: fill_mode={self.fill_mode}, время={settings.time_window_minutes}мин, системное время={settings.use_system_time}")
