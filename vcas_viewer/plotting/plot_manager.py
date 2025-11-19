# -*- coding: utf-8 -*-
"""
PlotManager - менеджер управления графиками и каналами
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from PyQt5.QtWidgets import QMessageBox
import logging
from typing import Dict, List, Optional, Set
import sys
import os
import time
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from vcas_viewer.models.channel_data import ChannelData
from .plot_dock_window import PlotDockWindow


class PlotManager(QObject):
    """
    Менеджер для управления графиками каналов, координации обновлений данных
    и взаимодействия с VCAS клиентом
    """

    # Сигналы
    channel_data_updated = pyqtSignal(str, object)  # channel_name, channel_data
    plot_window_created = pyqtSignal(object)  # plot_window
    plot_window_closed = pyqtSignal(object)  # plot_window
    plot_window_settings_changed = pyqtSignal(object)  # plot_window
    channels_changed = pyqtSignal(str)  # window_id - каналы в окне изменились

    def __init__(self, vcas_client=None, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('PlotManager')

        # VCAS клиент
        self.vcas_client = vcas_client

        # Окна графиков: window_id -> PlotDockWindow
        self.plot_windows: Dict[str, PlotDockWindow] = {}

        # Данные каналов: channel_name -> ChannelData
        self.channel_data: Dict[str, ChannelData] = {}

        # Подписки на каналы: channel_name -> set of window_ids
        self.channel_subscriptions: Dict[str, Set[str]] = {}

        # Таймер для периодического обновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_all_channels)
        self.update_timer.start(5000)  # Обновление каждые 5 секунд

        # Настройки
        self.max_windows = 30  # Максимальное количество окон графиков
        self.max_points_per_channel = 1000  # Максимальное количество точек на канал

        self.setup_connections()

    def setup_connections(self):
        """Настройка соединений сигналов"""
        if self.vcas_client:
            # Подключаемся к сигналам VCAS клиента
            self.vcas_client.channel_history_updated.connect(self._on_channel_history_updated)
            self.vcas_client.channel_info_updated.connect(self._on_channel_info_updated)

    def create_plot_window(self, title: str = "Графики каналов") -> Optional[PlotDockWindow]:
        """
        Создать новое окно графиков

        Args:
            title: Заголовок окна

        Returns:
            Созданное окно или None при ошибке
        """
        if len(self.plot_windows) >= self.max_windows:
            QMessageBox.warning(None, "Предупреждение",
                              f"Достигнуто максимальное количество окон графиков: {self.max_windows}")
            return None

        # Генерируем уникальный ID для окна
        window_id = f"plot_window_{len(self.plot_windows) + 1}"

        # Создаем окно
        plot_window = PlotDockWindow(title)
        plot_window.setObjectName(window_id)

        # Сохраняем в словаре
        self.plot_windows[window_id] = plot_window

        # Настраиваем соединения
        self._connect_plot_window_signals(plot_window, window_id)

        # Применяем значение по умолчанию для окна времени
        from vcas_viewer.core.config import Config
        default_time_window = Config.GRAPH_DEFAULT_TIME_WINDOW
        plot_window.set_time_window(default_time_window * 60)  # Конвертируем минуты в секунды

        # Отправляем сигнал
        self.plot_window_created.emit(plot_window)

        self.logger.info(f"Создано окно графиков: {window_id}")

        return plot_window

    def close_plot_window(self, plot_window: PlotDockWindow):
        """
        Закрыть окно графиков

        Args:
            plot_window: Окно для закрытия
        """
        # Находим ID окна
        window_id = None
        for wid, pw in self.plot_windows.items():
            if pw == plot_window:
                window_id = wid
                break

        if not window_id:
            return

        # Отписываемся от каналов этого окна
        channels_to_unsubscribe = []
        for channel_name, window_ids in self.channel_subscriptions.items():
            if window_id in window_ids:
                window_ids.remove(window_id)
                if not window_ids:  # Если больше нет подписчиков
                    channels_to_unsubscribe.append(channel_name)

        # Удаляем пустые подписки
        for channel_name in channels_to_unsubscribe:
            del self.channel_subscriptions[channel_name]

        # Закрываем окно
        plot_window.close()

        # Удаляем из словаря
        del self.plot_windows[window_id]

        # Отправляем сигнал
        self.plot_window_closed.emit(plot_window)

        self.logger.info(f"Закрыто окно графиков: {window_id}")

    def add_channel_to_window(self, channel_name: str, plot_window: PlotDockWindow):
        """
        Добавить канал в окно графиков

        Args:
            channel_name: Имя канала
            plot_window: Окно графиков
        """
        # Проверяем, существует ли канал
        if channel_name not in self.channel_data:
            # Создаем пустые данные канала
            self.channel_data[channel_name] = ChannelData(channel_name)

        # Добавляем канал в окно
        plot_window.add_channel(self.channel_data[channel_name])

        # Находим ID окна
        window_id = None
        for wid, pw in self.plot_windows.items():
            if pw == plot_window:
                window_id = wid
                break

        if window_id:
            # Добавляем подписку
            if channel_name not in self.channel_subscriptions:
                self.channel_subscriptions[channel_name] = set()
            self.channel_subscriptions[channel_name].add(window_id)

            # Запрашиваем данные канала
            self._request_channel_data(channel_name)

            # Отправляем сигнал об изменении каналов в окне
            self.channels_changed.emit(window_id)

        self.logger.info(f"Канал {channel_name} добавлен в окно {window_id}")

    def remove_channel_from_window(self, channel_name: str, plot_window: PlotDockWindow):
        """
        Удалить канал из окна графиков

        Args:
            channel_name: Имя канала
            plot_window: Окно графиков
        """
        # Удаляем канал из окна
        plot_window.remove_channel(channel_name)

        # Находим ID окна
        window_id = None
        for wid, pw in self.plot_windows.items():
            if pw == plot_window:
                window_id = wid
                break

        if window_id and channel_name in self.channel_subscriptions:
            # Удаляем подписку
            self.channel_subscriptions[channel_name].discard(window_id)
            if not self.channel_subscriptions[channel_name]:
                del self.channel_subscriptions[channel_name]

            # Отправляем сигнал об изменении каналов в окне
            self.channels_changed.emit(window_id)

        self.logger.info(f"Канал {channel_name} удален из окна {window_id}")

    def get_or_create_channel_data(self, channel_name: str) -> ChannelData:
        """
        Получить или создать данные канала

        Args:
            channel_name: Имя канала

        Returns:
            Объект ChannelData
        """
        if channel_name not in self.channel_data:
            self.channel_data[channel_name] = ChannelData(channel_name, use_system_time=True)

        return self.channel_data[channel_name]

    def update_channel_info(self, channel_name: str, info: dict):
        """
        Обновить информацию о канале

        Args:
            channel_name: Имя канала
            info: Информация о канале
        """
        channel_data = self.get_or_create_channel_data(channel_name)

        # Обновляем метаданные
        if 'descr' in info:
            channel_data.description = info['descr']
        if 'units' in info:
            channel_data.units = info['units']
        if 'type' in info:
            channel_data.metadata['type'] = info['type']

        self.logger.debug(f"Обновлена информация о канале {channel_name}")

    def _connect_plot_window_signals(self, plot_window: PlotDockWindow, window_id: str):
        """
        Подключить сигналы окна графиков

        Args:
            plot_window: Окно графиков
            window_id: ID окна
        """
        plot_window.channel_requested.connect(self._on_channel_requested)
        plot_window.window_closed.connect(lambda: self.close_plot_window(plot_window))
        plot_window.settings_changed.connect(lambda: self._on_plot_window_settings_changed(plot_window))

    def _on_channel_requested(self, channel_name: str):
        """
        Обработчик запроса данных канала

        Args:
            channel_name: Имя канала
        """
        self._request_channel_data(channel_name)

    def _request_channel_data(self, channel_name: str):
        """
        Запросить данные канала у VCAS клиента

        Args:
            channel_name: Имя канала
        """
        if not self.vcas_client or not self.vcas_client.is_connected:
            self.logger.warning("VCAS клиент не подключен, пропускаем запрос данных")
            return

        try:
            # Запрашиваем информацию о канале
            self.vcas_client.get_channel_info(channel_name)

            # Запрашиваем исторические данные
            self.vcas_client.get_channel_history(channel_name, duration_seconds=300)

        except Exception as e:
            self.logger.error(f"Ошибка запроса данных канала {channel_name}: {e}")

    def _on_channel_info_updated(self, channel_info):
        """
        Обработчик обновления информации о канале

        Args:
            channel_info: Информация о канале
        """
        try:
            if isinstance(channel_info, dict):
                if 'multiple' in channel_info:
                    # Множественное обновление
                    for info in channel_info.get('channels', []):
                        self._process_single_channel_info(info)
                else:
                    # Одиночное обновление
                    self._process_single_channel_info(channel_info)

        except Exception as e:
            self.logger.error(f"Ошибка обработки обновления информации о канале: {e}")

    def _process_single_channel_info(self, info: dict):
        """
        Обработать информацию об одном канале

        Args:
            info: Информация о канале
        """
        channel_name = info.get('name', '')
        if not channel_name:
            return

        # Обновляем информацию о канале
        self.update_channel_info(channel_name, info)

        # Получаем значение канала
        val = info.get('val', '')
        if val:
            try:
                # Конвертируем значение
                if isinstance(val, str):
                    # Пытаемся конвертировать в число
                    try:
                        val = float(val)
                    except ValueError:
                        pass  # Оставляем как строку

                # Добавляем точку данных с системным временем для новых данных
                channel_data = self.get_or_create_channel_data(channel_name)
                import time
                channel_data.add_data_point(time.time(), val)

                # Ограничиваем количество точек
                channel_data.limit_data_points(self.max_points_per_channel)

                # Отправляем сигнал обновления
                self.channel_data_updated.emit(channel_name, channel_data)

            except Exception as e:
                self.logger.error(f"Ошибка обработки значения канала {channel_name}: {e}")

    def _on_channel_history_updated(self, history_data):
        """
        Обработчик обновления исторических данных канала

        Args:
            history_data: Исторические данные канала
        """
        try:
            channel_name = history_data.get('channel', history_data.get('name', ''))
            if not channel_name:
                return

            # Получаем данные
            timestamps = history_data.get('timestamps', [])
            values = history_data.get('values', [])

            if not timestamps or not values:
                return

            # Создаем или получаем данные канала
            channel_data = self.get_or_create_channel_data(channel_name)

            # Добавляем исторические данные, используя серверные timestamps (use_system_time=False)
            channel_data.add_data_points(timestamps, values, use_system_time=False)

            # Ограничиваем количество точек
            channel_data.limit_data_points(self.max_points_per_channel)

            # Отправляем сигнал обновления
            self.channel_data_updated.emit(channel_name, channel_data)

            self.logger.debug(f"Обновлены исторические данные канала {channel_name}: {len(timestamps)} точек")

        except Exception as e:
            self.logger.error(f"Ошибка обработки исторических данных канала: {e}")

    def _update_all_channels(self):
        """Периодическое обновление всех каналов"""
        if not self.vcas_client or not self.vcas_client.is_connected:
            return

        try:
            # Обновляем информацию о всех подписанных каналах
            for channel_name in self.channel_subscriptions.keys():
                self.vcas_client.get_channel_info(channel_name)

        except Exception as e:
            self.logger.error(f"Ошибка периодического обновления каналов: {e}")

    def get_channel_names(self) -> List[str]:
        """
        Получить список всех каналов

        Returns:
            Список имен каналов
        """
        return list(self.channel_data.keys())

    def get_subscribed_channels(self) -> List[str]:
        """
        Получить список подписанных каналов

        Returns:
            Список имен каналов
        """
        return list(self.channel_subscriptions.keys())

    def get_window_count(self) -> int:
        """
        Получить количество окон графиков

        Returns:
            Количество окон
        """
        return len(self.plot_windows)

    def get_channel_count(self) -> int:
        """
        Получить общее количество каналов

        Returns:
            Количество каналов
        """
        return len(self.channel_data)

    def clear_all_data(self):
        """Очистить все данные каналов"""
        self.channel_data.clear()
        self.channel_subscriptions.clear()

        # Очищаем все окна
        for plot_window in list(self.plot_windows.values()):
            plot_window.clear_all_channels()

        self.logger.info("Все данные каналов очищены")

    def export_channel_data(self, channel_name: str) -> Optional[dict]:
        """
        Экспортировать данные канала

        Args:
            channel_name: Имя канала

        Returns:
            Словарь с данными канала или None
        """
        if channel_name not in self.channel_data:
            return None

        channel_data = self.channel_data[channel_name]
        timestamps, values = channel_data.get_data_arrays()

        return {
            'name': channel_data.name,
            'description': channel_data.description,
            'units': channel_data.units,
            'timestamps': timestamps.tolist() if len(timestamps) > 0 else [],
            'values': values.tolist() if len(values) > 0 else [],
            'metadata': channel_data.metadata,
            'display_settings': channel_data.display_settings
        }

    def get_window_info(self, window_id: str) -> dict:
        """
        Получить информацию об окне графиков

        Args:
            window_id: ID окна

        Returns:
            Словарь с информацией об окне или пустой словарь
        """
        if window_id not in self.plot_windows:
            return {}

        plot_window = self.plot_windows[window_id]
        channels_list = plot_window.get_channels_list()

        # Получаем окно времени из первого графика (все графики в окне имеют одинаковое время)
        time_window_minutes = 5  # значение по умолчанию
        if plot_window.plot_container.plot_widgets:
            first_plot = plot_window.plot_container.plot_widgets[0]
            time_window_seconds = first_plot.get_time_window()
            time_window_minutes = time_window_seconds // 60

        return {
            'title': plot_window.windowTitle(),
            'channels': channels_list,
            'time_window': time_window_minutes,
            'channels_count': len(channels_list)
        }

    def get_all_windows_info(self) -> list:
        """
        Получить информацию о всех окнах графиков

        Returns:
            Список словарей с информацией об окнах
        """
        windows_info = []
        for window_id in self.plot_windows.keys():
            info = self.get_window_info(window_id)
            if info:
                info['window_id'] = window_id
                windows_info.append(info)

        return windows_info

    def rename_window(self, window_id: str, new_title: str):
        """
        Переименовать окно графиков

        Args:
            window_id: ID окна
            new_title: Новое название
        """
        if window_id not in self.plot_windows:
            self.logger.warning(f"Окно {window_id} не найдено")
            return

        plot_window = self.plot_windows[window_id]
        plot_window.setWindowTitle(new_title)

        # Отправляем сигнал об изменении настроек окна
        self.plot_window_settings_changed.emit(plot_window)

        self.logger.info(f"Окно {window_id} переименовано в '{new_title}'")

    def set_vcas_client(self, vcas_client):
        """
        Установить VCAS клиент

        Args:
            vcas_client: VCAS клиент
        """
        # Отключаем старые соединения
        if self.vcas_client:
            try:
                self.vcas_client.channel_history_updated.disconnect(self._on_channel_history_updated)
                self.vcas_client.channel_info_updated.disconnect(self._on_channel_info_updated)
            except:
                pass

        # Устанавливаем нового клиента
        self.vcas_client = vcas_client

        # Подключаем новые соединения
        if self.vcas_client:
            self.vcas_client.channel_history_updated.connect(self._on_channel_history_updated)
            self.vcas_client.channel_info_updated.connect(self._on_channel_info_updated)

        self.logger.info("VCAS клиент обновлен")

    def export_window_data(self, window_id: str, time_range: tuple = None) -> str:
        """
        Экспортировать данные окна в CSV

        Args:
            window_id: ID окна
            time_range: Диапазон времени (start, end) или None для всех данных

        Returns:
            Путь к сохраненному файлу или пустая строка при ошибке
        """
        if window_id not in self.plot_windows:
            self.logger.error(f"Окно {window_id} не найдено")
            return ""

        try:
            # Создаем директорию если не существует
            export_dir = "!data_exports"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)

            plot_window = self.plot_windows[window_id]
            channels_list = plot_window.get_channels_list()

            if not channels_list:
                self.logger.warning(f"В окне {window_id} нет каналов для экспорта")
                return ""

            # Генерируем имя файла
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            # Заменяем слеши в именах каналов на безопасные символы
            safe_channels = [ch.replace('/', '_').replace('\\', '_') for ch in channels_list[:3]]
            channels_part = "_".join(safe_channels)  # Первые 3 канала
            if len(channels_list) > 3:
                channels_part += f"_and_{len(channels_list) - 3}_more"
            filename = f"{timestamp}_{channels_part}.csv"
            filepath = os.path.join(export_dir, filename)

            # Собираем данные
            import csv
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Заголовки
                headers = ['timestamp']
                for channel_name in channels_list:
                    headers.extend([f'{channel_name}_time', f'{channel_name}_value'])
                writer.writerow(headers)

                # Получаем все временные метки
                all_timestamps = set()
                channel_data_map = {}

                for channel_name in channels_list:
                    if channel_name in self.channel_data:
                        channel_data = self.channel_data[channel_name]
                        timestamps, values = channel_data.get_data_arrays()
                        if len(timestamps) > 0:
                            all_timestamps.update(timestamps)
                            channel_data_map[channel_name] = dict(zip(timestamps, values))

                # Сортируем временные метки
                sorted_timestamps = sorted(all_timestamps)

                # Фильтруем по диапазону если указан
                if time_range:
                    start_time, end_time = time_range
                    sorted_timestamps = [t for t in sorted_timestamps if start_time <= t <= end_time]

                # Записываем данные
                for timestamp in sorted_timestamps:
                    row = [timestamp]
                    for channel_name in channels_list:
                        if channel_name in channel_data_map and timestamp in channel_data_map[channel_name]:
                            row.extend([timestamp, channel_data_map[channel_name][timestamp]])
                        else:
                            row.extend([timestamp, ''])  # Пустое значение если данных нет
                    writer.writerow(row)

            self.logger.info(f"Данные окна {window_id} экспортированы в {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Ошибка экспорта данных окна {window_id}: {e}")
            return ""

    def export_window_config(self, window_id: str) -> dict:
        """
        Экспортировать конфигурацию окна

        Args:
            window_id: ID окна

        Returns:
            Словарь с конфигурацией или пустой словарь при ошибке
        """
        if window_id not in self.plot_windows:
            self.logger.error(f"Окно {window_id} не найдено")
            return {}

        try:
            plot_window = self.plot_windows[window_id]
            window_info = self.get_window_info(window_id)

            config = {
                'window_id': window_id,
                'title': window_info.get('title', ''),
                'channels': window_info.get('channels', []),
                'time_window': window_info.get('time_window', 5),
                'export_timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            self.logger.debug(f"Конфигурация окна {window_id} экспортирована")
            return config

        except Exception as e:
            self.logger.error(f"Ошибка экспорта конфигурации окна {window_id}: {e}")
            return {}

    def save_window_config_to_file(self, window_id: str, directory: str = "!window_configs") -> str:
        """
        Сохранить конфигурацию окна в JSON файл

        Args:
            window_id: ID окна
            directory: Директория для сохранения

        Returns:
            Путь к сохраненному файлу или пустая строка при ошибке
        """
        try:
            # Создаем директорию если не существует
            if not os.path.exists(directory):
                os.makedirs(directory)

            config = self.export_window_config(window_id)
            if not config:
                return ""

            # Генерируем имя файла
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            title = config.get('title', 'window').replace(' ', '_')
            filename = f"{timestamp}_{title}_config.json"
            filepath = os.path.join(directory, filename)

            # Сохраняем в JSON
            import json
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Конфигурация окна {window_id} сохранена в {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации окна {window_id}: {e}")
            return ""

    def save_window_screenshot(self, window_id: str, directory: str = "!data_exports") -> str:
        """
        Создать скриншот окна графика

        Args:
            window_id: ID окна
            directory: Директория для сохранения

        Returns:
            Путь к сохраненному файлу или пустая строка при ошибке
        """
        if window_id not in self.plot_windows:
            self.logger.error(f"Окно {window_id} не найдено")
            return ""

        try:
            # Создаем директорию если не существует
            if not os.path.exists(directory):
                os.makedirs(directory)

            plot_window = self.plot_windows[window_id]

            # Получаем содержимое окна
            pixmap = plot_window.grab()

            # Генерируем имя файла
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            title = plot_window.windowTitle().replace(' ', '_')
            filename = f"{timestamp}_{title}_screenshot.png"
            filepath = os.path.join(directory, filename)

            # Сохраняем как PNG
            if pixmap.save(filepath, 'PNG'):
                self.logger.info(f"Скриншот окна {window_id} сохранен в {filepath}")
                return filepath
            else:
                self.logger.error(f"Не удалось сохранить скриншот окна {window_id}")
                return ""

        except Exception as e:
            self.logger.error(f"Ошибка создания скриншота окна {window_id}: {e}")
            return ""

    def get_saved_configs_list(self, directory: str = "!window_configs") -> List[dict]:
        """
        Получить список сохраненных конфигураций окон

        Args:
            directory: Директория с конфигурациями

        Returns:
            Список словарей с информацией о конфигурациях
        """
        configs_list = []

        try:
            if not os.path.exists(directory):
                return configs_list

            # Ищем все JSON файлы конфигураций
            for filename in os.listdir(directory):
                if filename.endswith('_config.json'):
                    filepath = os.path.join(directory, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            config = json.load(f)

                        # Добавляем информацию о файле
                        config_info = {
                            'filepath': filepath,
                            'filename': filename,
                            'title': config.get('title', 'Без названия'),
                            'channels': config.get('channels', []),
                            'time_window': config.get('time_window', 5),
                            'export_timestamp': config.get('export_timestamp', ''),
                            'channels_count': len(config.get('channels', []))
                        }
                        configs_list.append(config_info)

                    except Exception as e:
                        self.logger.warning(f"Ошибка чтения конфигурации {filepath}: {e}")

            # Сортируем по времени сохранения (новые сверху)
            configs_list.sort(key=lambda x: x.get('export_timestamp', ''), reverse=True)

        except Exception as e:
            self.logger.error(f"Ошибка получения списка конфигураций: {e}")

        return configs_list

    def load_window_config_from_file(self, filepath: str) -> Optional[PlotDockWindow]:
        """
        Загрузить конфигурацию окна из файла и создать окно

        Args:
            filepath: Путь к файлу конфигурации

        Returns:
            Созданное окно или None при ошибке
        """
        try:
            # Читаем конфигурацию
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)

            title = config.get('title', 'Загруженное окно')
            channels = config.get('channels', [])
            time_window = config.get('time_window', 5)

            # Создаем новое окно
            plot_window = self.create_plot_window(title)
            if not plot_window:
                self.logger.error("Не удалось создать окно для загрузки конфигурации")
                return None

            # Устанавливаем окно времени
            plot_window.set_time_window(time_window * 60)  # Конвертируем минуты в секунды

            # Добавляем каналы
            for channel_name in channels:
                self.add_channel_to_window(channel_name, plot_window)

            self.logger.info(f"Конфигурация загружена из {filepath}: окно '{title}' с {len(channels)} каналами")
            return plot_window

        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации из {filepath}: {e}")
            return None

    def _on_plot_window_settings_changed(self, plot_window: PlotDockWindow):
        """
        Обработчик изменения настроек окна графиков

        Args:
            plot_window: Окно графиков, настройки которого изменились
        """
        self.logger.debug("Настройки окна графиков изменены")
        self.plot_window_settings_changed.emit(plot_window)
