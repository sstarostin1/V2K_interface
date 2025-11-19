# -*- coding: utf-8 -*-
"""
ChannelData - класс для хранения данных каналов с поддержкой временных рядов
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
import time
import logging


class ChannelData:
    """Класс для хранения данных каналов с поддержкой временных рядов"""

    def __init__(self, name: str, description: str = "", units: str = "", use_system_time: bool = True):
        """
        Инициализация данных канала

        Args:
            name: Имя канала
            description: Описание канала
            units: Единицы измерения
            use_system_time: Использовать системное время машины вместо серверного
        """
        self.name = name
        self.description = description
        self.units = units
        self.use_system_time = use_system_time  # Новый флаг
        self.logger = logging.getLogger(f'ChannelData.{name}')

        # Данные временных рядов: список пар (timestamp, value)
        self.data: List[Tuple[float, float]] = []

        # Метаданные канала
        self.metadata: Dict[str, Any] = {
            'type': 'unknown',
            'min_value': None,
            'max_value': None,
            'last_update': None,
            'data_points': 0,
            'use_system_time': use_system_time  # Сохраняем в метаданных
        }

        # Настройки отображения
        self.display_settings = {
            'color': None,  # Будет назначен автоматически
            'visible': True,
            'line_width': 2,
            'symbol': 'o',
            'symbol_size': 4
        }

    def add_data_point(self, timestamp, value, use_system_time=None):
        """
        Добавить точку данных

        Args:
            timestamp: Временная метка (Unix timestamp или строка)
            value: Значение (число или строка)
            use_system_time: Принудительно использовать системное время (True), 
                           серверное (False) или по настройке канала (None)
        """
        try:
            # Конвертируем timestamp в float если нужно
            if isinstance(timestamp, str):
                # Предполагаем формат DD.MM.YYYY HH_MM_SS.fffff
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp, '%d.%m.%Y %H_%M_%S.%f')
                    timestamp = dt.timestamp()
                except ValueError:
                    timestamp = float(timestamp)

            # Проверяем и конвертируем value
            if isinstance(value, str):
                lower_val = value.lower()
                if lower_val in ('none', 'null', 'nan', ''):
                    # Отмечаем канал как содержащий невалидные данные
                    self.metadata['invalid_data'] = True
                    self.logger.warning(f"Канал {self.name} содержит невалидное значение: {value} на timestamp {timestamp}")
                    return
                elif lower_val == 'error':
                    # Сервер вернул ошибку для запроса истории
                    self.metadata['history_error'] = True
                    self.logger.warning(f"Сервер вернул ошибку истории для канала {self.name}")
                    return
                else:
                    # Пытаемся конвертировать в число
                    value = float(value)

            # Определяем, использовать ли системное время
            use_sys_time = self.use_system_time if use_system_time is None else use_system_time

            # Если используется системное время, заменяем timestamp на текущее время
            if use_sys_time:
                server_timestamp = timestamp
                timestamp = time.time()
                self.logger.debug(f"Используем системное время {timestamp:.1f} вместо серверного {server_timestamp:.1f} для канала {self.name}")

            # Добавляем точку только с валидным значением
            self.data.append((timestamp, value))

            # Обновляем метаданные
            self.metadata['last_update'] = timestamp
            self.metadata['data_points'] = len(self.data)
            self.metadata['invalid_data'] = False  # Сбрасываем флаг при получении валидных данных

            # Обновляем min/max значения
            if self.metadata['min_value'] is None or value < self.metadata['min_value']:
                self.metadata['min_value'] = value
            if self.metadata['max_value'] is None or value > self.metadata['max_value']:
                self.metadata['max_value'] = value

            self.logger.debug(f"Добавлена точка: timestamp={timestamp:.1f}, value={value}")

        except (ValueError, TypeError) as e:
            self.logger.error(f"Ошибка добавления точки данных timestamp={timestamp}, value={value}: {e}")

    def add_data_points(self, timestamps: List[float], values: List[float], use_system_time=None):
        """
        Добавить несколько точек данных

        Args:
            timestamps: Список временных меток
            values: Список значений
            use_system_time: Принудительно использовать системное время (True),
                           серверное (False) или по настройке канала (None)
        """
        if len(timestamps) != len(values):
            self.logger.error("Несоответствие размеров списков timestamps и values")
            return

        for ts, val in zip(timestamps, values):
            self.add_data_point(ts, val, use_system_time)

    def get_data_arrays(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Получить данные в виде numpy массивов для графиков

        Returns:
            Кортеж (timestamps, values)
        """
        if not self.data:
            return np.array([]), np.array([])

        timestamps, values = zip(*self.data)
        return np.array(timestamps), np.array(values)

    def get_latest_value(self) -> Optional[float]:
        """
        Получить последнее значение

        Returns:
            Последнее значение или None если данных нет
        """
        if self.data:
            return self.data[-1][1]
        return None

    def get_latest_timestamp(self) -> Optional[float]:
        """
        Получить временную метку последнего значения

        Returns:
            Временная метка или None если данных нет
        """
        if self.data:
            return self.data[-1][0]
        return None

    def clear_data(self):
        """Очистить все данные"""
        self.data.clear()
        self.metadata['min_value'] = None
        self.metadata['max_value'] = None
        self.metadata['data_points'] = 0
        self.metadata['last_update'] = None
        self.logger.debug("Данные канала очищены")

    def limit_data_points(self, max_points: int):
        """
        Ограничить количество точек данных

        Args:
            max_points: Максимальное количество точек
        """
        if len(self.data) > max_points:
            # Оставляем последние max_points точек
            self.data = self.data[-max_points:]
            self.metadata['data_points'] = len(self.data)

            # Пересчитываем min/max
            if self.data:
                values = [point[1] for point in self.data]
                self.metadata['min_value'] = min(values)
                self.metadata['max_value'] = max(values)

            self.logger.debug(f"Данные ограничены до {max_points} точек")

    def get_time_range(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Получить диапазон времени данных

        Returns:
            Кортеж (min_time, max_time) или (None, None) если данных нет
        """
        if not self.data:
            return None, None

        timestamps = [point[0] for point in self.data]
        return min(timestamps), max(timestamps)

    def get_value_range(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Получить диапазон значений данных

        Returns:
            Кортеж (min_value, max_value) или (None, None) если данных нет
        """
        if not self.data:
            return None, None

        values = [point[1] for point in self.data]
        return min(values), max(values)

    def set_display_color(self, color: str):
        """
        Установить цвет отображения

        Args:
            color: Цвет в формате hex (#RRGGBB) или имени
        """
        self.display_settings['color'] = color

    def set_visibility(self, visible: bool):
        """
        Установить видимость канала

        Args:
            visible: True для отображения, False для скрытия
        """
        self.display_settings['visible'] = visible

    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализовать данные канала в словарь

        Returns:
            Словарь с данными канала
        """
        return {
            'name': self.name,
            'description': self.description,
            'units': self.units,
            'data': self.data,
            'metadata': self.metadata,
            'display_settings': self.display_settings
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChannelData':
        """
        Создать объект ChannelData из словаря

        Args:
            data: Словарь с данными канала

        Returns:
            Объект ChannelData
        """
        channel = cls(
            name=data['name'],
            description=data.get('description', ''),
            units=data.get('units', '')
        )

        channel.data = data.get('data', [])
        channel.metadata = data.get('metadata', channel.metadata)
        channel.display_settings = data.get('display_settings', channel.display_settings)

        return channel

    def __len__(self) -> int:
        """Количество точек данных"""
        return len(self.data)

    def __str__(self) -> str:
        """Строковое представление"""
        return f"ChannelData(name='{self.name}', points={len(self.data)}, units='{self.units}')"

    def __repr__(self) -> str:
        """Представление для отладки"""
        return self.__str__()
