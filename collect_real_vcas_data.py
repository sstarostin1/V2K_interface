#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для сбора данных каналов с реального VCAS сервера ВЭПП-2000
Используется для улучшения mock-сервера для оффлайн отладки
"""

import socket
import time
import json
import logging
from datetime import datetime
import sys
import os

# Добавляем путь к модулям проекта для импорта VCASClient
sys.path.insert(0, os.path.dirname(__file__))
from vcas_viewer.core.logging_config import configure_logging

# Настройки подключения к реальному серверу
REAL_VCAS_HOST = "172.16.1.110"
REAL_VCAS_PORT = 20041

# Настройки сбора данных
MAX_CHANNELS = 400
BASIC_DIRECTORIES = [
    "VEPP", "BEP", "Diagnostics", "Magnets", "RF", "Vacuum", "Temperature", "TEST", "DEBUG"
]

# Настройки вывода
OUTPUT_FILE = "real_vcas_channels_data.json"

class VCASDataCollector:
    """Класс для сбора данных с VCAS сервера"""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.logger = logging.getLogger('VCASDataCollector')
        self.collected_data = {
            "metadata": {
                "collection_time": None,
                "server_address": f"{host}:{port}",
                "total_channels_available": 0,
                "channels_collected": 0,
                "errors_count": 0
            },
            "directories": {},
            "channel_details": {}
        }

    def connect(self):
        """Подключение к VCAS серверу"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.logger.info(f"Подключено к VCAS серверу {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка подключения к серверу: {str(e)}")
            return False

    def send_command(self, command):
        """Отправка команды на сервер"""
        if not self.socket:
            return None

        try:
            self.socket.send((command + '\n').encode('utf-8'))
            response = self.receive_response()
            return response

        except Exception as e:
            self.logger.error(f"Ошибка отправки команды: {str(e)}")
            return None

    def receive_response(self):
        """Получение ответа от сервера"""
        if not self.socket:
            return ""

        buffer = b""
        try:
            while True:
                data = self.socket.recv(1024)
                if not data:
                    break
                buffer += data
                if b'\n' in buffer:
                    # Нашли завершение строки
                    end_pos = buffer.index(b'\n')
                    response = buffer[:end_pos].decode('utf-8')
                    # Оставляем остаток в буфере для следующего чтения
                    buffer = buffer[end_pos + 1:]
                    return response
        except Exception as e:
            self.logger.error(f"Ошибка получения ответа: {str(e)}")
            return ""

    def get_channels_list(self):
        """Получение списка каналов"""
        command = "method:get|name:ChannelsList"
        response = self.send_command(command)

        if response:
            # Парсим ответ
            parts = response.split('|')
            for part in parts:
                if part.startswith('val:'):
                    channels_str = part[4:]  # Убираем 'val:'
                    channels = [ch.strip() for ch in channels_str.split(',') if ch.strip()]
                    self.logger.info(f"Получено {len(channels)} каналов от сервера")
                    self.collected_data["metadata"]["total_channels_available"] = len(channels)
                    return channels

        self.logger.error("Не удалось получить список каналов")
        return []

    def get_channel_info(self, channel_name):
        """Получение детальной информации о канале"""
        command = f"method:getfull|name:{channel_name}"
        response = self.send_command(command)

        if response:
            try:
                # Парсим ответ
                info = {}
                parts = response.split('|')
                for part in parts:
                    if ':' in part:
                        key, value = part.split(':', 1)
                        info[key.strip()] = value.strip()

                # Добавляем имя канала, если не указано
                if 'name' not in info:
                    info['name'] = channel_name

                return info
            except Exception as e:
                self.logger.error(f"Ошибка парсинга информации о канале {channel_name}: {str(e)}")

        return None

    def collect_channels_info(self, channels_list, max_channels=MAX_CHANNELS):
        """Сбор информации о каналах с учетом ограничений"""

        # Создаем лог-файл для детального вывода
        log_filename = f"collection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(log_filename, 'w', encoding='utf-8') as log_file:
            def write_log(message):
                log_file.write(f"{datetime.now().isoformat()} - {message}\n")
                log_file.flush()

            write_log("Начало сбора информации о каналах")

            # Группируем каналы по директориям
            directories = {}
            for channel in channels_list:
                # Получаем корневую директорию
                root_dir = channel.split('/')[0] if '/' in channel else channel

                if root_dir not in directories:
                    directories[root_dir] = []
                directories[root_dir].append(channel)

            write_log(f"Найдено {len(directories)} директорий:")
            for dir_name, dir_channels in directories.items():
                write_log(f"  {dir_name}: {len(dir_channels)} каналов")

            # Сохраняем структуру директорий
            self.collected_data["directories"] = directories

            # Выбираем каналы для сбора
            selected_channels = []
            basic_channels = []
            other_channels = []

            for dir_name, dir_channels in directories.items():
                if dir_name in BASIC_DIRECTORIES:
                    selected_channels.extend(dir_channels)
                    basic_channels.extend(dir_channels)
                else:
                    other_channels.extend(dir_channels)

            write_log(f"Каналы из основных директорий: {len(basic_channels)}")

            # Добавляем остальные каналы до достижения лимита
            remaining_slots = max_channels - len(basic_channels)
            if remaining_slots > 0 and other_channels:
                additional_channels = other_channels[:remaining_slots]
                selected_channels.extend(additional_channels)
                write_log(f"Добавлено дополнительных каналов: {len(additional_channels)}")

            # Ограничиваем общее количество
            if len(selected_channels) > max_channels:
                selected_channels = selected_channels[:max_channels]

            write_log(f"Всего каналов для сбора информации: {len(selected_channels)}")

            # Собираем информацию
            collected_count = 0
            error_count = 0

            for i, channel in enumerate(selected_channels, 1):
                info = self.get_channel_info(channel)
                if info:
                    self.collected_data["channel_details"][channel] = info
                    collected_count += 1
                    write_log(f"OK {i:3d}: {channel}")
                else:
                    error_count += 1
                    write_log(f"FAIL {i:3d}: {channel}")

                time.sleep(0.05)  # Пауза между запросами

            self.collected_data["metadata"]["channels_collected"] = collected_count
            self.collected_data["metadata"]["errors_count"] = error_count
            write_log(f"Сбор завершен: {collected_count} OK, {error_count} FAIL")

    def save_data(self, filename=OUTPUT_FILE):
        """Сохранение собранных данных в файл"""
        self.collected_data["metadata"]["collection_time"] = datetime.now().isoformat()

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.collected_data, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"Данные сохранены в файл {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения данных: {str(e)}")
            return False

    def disconnect(self):
        """Отключение от сервера"""
        if self.socket:
            try:
                self.socket.close()
                self.socket = None
                self.logger.info("Отключено от VCAS сервера")
            except Exception as e:
                self.logger.error(f"Ошибка при отключении: {str(e)}")

    def run_collection(self):
        """Основной метод сбора данных"""
        try:
            if not self.connect():
                return False

            channels_list = self.get_channels_list()
            if not channels_list:
                return False

            self.collect_channels_info(channels_list)
            self.save_data()

            return True

        except Exception as e:
            self.logger.error(f"Критическая ошибка при сборе данных: {str(e)}")
            return False
        finally:
            self.disconnect()


def main():
    """Главная функция"""
    # Настраиваем логирование
    configure_logging("minimal", "minimal")

    # Создаем коллектор
    collector = VCASDataCollector(REAL_VCAS_HOST, REAL_VCAS_PORT)

    # Запускаем сбор данных
    success = collector.run_collection()

    print(f"{'Сбор данных завершен успешно' if success else 'Ошибка при сборе данных'}")
    if success:
        print(f"Данные сохранены в файл: {OUTPUT_FILE}")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
