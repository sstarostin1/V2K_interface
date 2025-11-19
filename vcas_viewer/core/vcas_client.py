# -*- coding: utf-8 -*-
"""
VCAS клиент для работы с сервером каналов
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QByteArray
from PyQt5.QtNetwork import QTcpSocket, QAbstractSocket
import logging
import sys


class VCASClient(QObject):
    """Клиент для работы с VCAS сервером"""

    # Сигналы
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    channels_updated = pyqtSignal(list)
    channel_info_updated = pyqtSignal(dict)
    channel_history_updated = pyqtSignal(dict)

    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.is_connected = False
        self.socket = None
        self.channels_list = []
        self.channel_info_cache = {}
        self.channel_history_cache = {}  # Кэш исторических данных
        self.pending_requests = {}  # Для отслеживания запросов

        # Для множественного запроса
        self.multiple_request_pending = None
        self.multiple_info = {}

        # Настройка логирования
        self.logger = logging.getLogger('VCASClient')

        # Таймер для периодического обновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_channels)

        # Буфер для входящих данных
        self.buffer = QByteArray()

    def connect_to_server(self):
        """Подключение к VCAS серверу"""
        try:
            # Создаем сокет
            self.socket = QTcpSocket()
            self.socket.connected.connect(self._on_connected)
            self.socket.disconnected.connect(self._on_disconnected)
            self.socket.error.connect(self._on_error)
            self.socket.readyRead.connect(self._on_ready_read)
            self.socket.stateChanged.connect(self._on_state_changed)

            self.logger.info(f"Подключение к VCAS серверу {self.host}:{self.port}")
            self.socket.connectToHost(self.host, self.port)

        except Exception as e:
            error_msg = f"Ошибка создания сокета: {str(e)}"
            self.logger.error(error_msg)
            self.error.emit(error_msg)

    def _on_connected(self):
        """Обработчик успешного подключения"""
        self.is_connected = True
        self.connected.emit()
        self.logger.info("Успешно подключено к VCAS серверу")

        # Запускаем периодическое обновление списка каналов
        self.update_timer.start(30000)  # 30 секунд
        self.logger.debug("Запущен таймер периодического обновления каналов (30 секунд)")

        # Получаем список каналов сразу после подключения
        self.logger.debug("Запуск получения списка каналов после подключения")
        self._update_channels()

    def _on_disconnected(self):
        """Обработчик отключения"""
        self.is_connected = False
        self.disconnected.emit()
        self.logger.info("Отключено от VCAS сервера")

        # Останавливаем таймер
        if self.update_timer.isActive():
            self.update_timer.stop()

    def _on_error(self, error):
        """Обработчик ошибок сокета"""
        error_msg = f"Ошибка сокета: {self.socket.errorString()}"
        self.logger.error(error_msg)
        self.error.emit(error_msg)

    def _on_state_changed(self, state):
        """Обработчик изменения состояния сокета"""
        self.logger.debug(f"Состояние сокета изменено: {state}")

    def _on_ready_read(self):
        """Обработчик входящих данных"""
        try:
            data = self.socket.readAll()
            self.buffer.append(data)

            # Обрабатываем полученные данные
            self._process_buffer()

        except Exception as e:
            self.logger.error(f"Ошибка при чтении данных: {str(e)}")

    def _process_buffer(self):
        """Обработка буфера входящих данных"""
        try:
            # Ищем завершающие символы новой строки
            while b'\n' in self.buffer:
                # Находим позицию первого завершения строки
                newline_pos = self.buffer.indexOf(b'\n')

                # Извлекаем строку
                line_data = self.buffer.left(newline_pos)
                self.buffer.remove(0, newline_pos + 1)

                # Декодируем и обрабатываем строку
                if line_data.size() > 0:
                    try:
                        line = line_data.data().decode('utf-8').strip()
                        if line:
                            self._process_message(line)
                    except UnicodeDecodeError:
                        self.logger.warning(f"Ошибка декодирования строки: {line_data.data()}")

        except Exception as e:
            self.logger.error(f"Ошибка обработки буфера: {str(e)}")

    def _process_message(self, message):
        """Обработка полученного сообщения"""
        try:
            self.logger.info(f"Получено сообщение от сервера: {message}")

            # Парсим сообщение VCAS протокола
            # Формат: key1:value1|key2:value2
            if ':' not in message:
                return

            # Разбиваем на пары ключ-значение
            pairs = message.split('|')
            msg_dict = {}

            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    msg_dict[key.strip()] = value.strip()

            if msg_dict:
                self._handle_message(msg_dict)

        except Exception as e:
            self.logger.error(f"Ошибка обработки сообщения '{message}': {str(e)}")

    def _handle_message(self, msg_dict):
        """Обработка распарсенного сообщения"""
        # Обрабатываем ответ на запрос списка каналов
        if 'name' in msg_dict and msg_dict.get('name') == 'ChannelsList':
            self._handle_channels_list(msg_dict)
        elif 'method' in msg_dict and msg_dict.get('method') == 'gethistory':
            # Обрабатываем ответ на запрос исторических данных
            self._handle_channel_history(msg_dict)
        else:
            # Обрабатываем ответ на запрос информации о канале
            self._handle_channel_info(msg_dict)

    def _handle_channels_list(self, msg_dict):
        """Обработка ответа со списком каналов"""
        try:
            val = msg_dict.get('val', '')
            if val and val != 'none':
                # Разбиваем строку на список каналов
                channels = [ch.strip() for ch in val.split(',') if ch.strip()]

                # Проверяем, изменился ли список каналов
                if self._channels_changed(channels):
                    self.channels_list = channels
                    self.logger.info(f"VCASClient: список каналов изменился, получено {len(channels)} каналов")
                    self.logger.debug(f"Первые 5 каналов: {channels[:5]}")

                    # Отправляем сигнал обновления
                    self.channels_updated.emit(channels)
                    self.logger.info(f"VCASClient: отправлен сигнал channels_updated с {len(channels)} каналами")
                else:
                    self.logger.debug("VCASClient: список каналов не изменился, обновление пропущено")
            else:
                self.logger.warning("VCASClient: получен пустой список каналов от сервера")
        except Exception as e:
            self.logger.error(f"VCASClient: ошибка обработки списка каналов: {str(e)}")

    def _handle_channel_info(self, msg_dict):
        """Обработка ответа с информацией о канале"""
        try:
            # Определяем имя канала из ответа
            channel_name = msg_dict.get('name', '')

            if channel_name:
                # Добавляем имя канала в ответ
                info = msg_dict.copy()
                info['name'] = channel_name

                # Сохраняем в кэш
                self.channel_info_cache[channel_name] = info

                # Проверяем, является ли это частью множественного запроса
                if self.multiple_request_pending and channel_name in self.multiple_request_pending:
                    self.multiple_info[channel_name] = info

                    # Проверяем, все ли данные получены
                    if len(self.multiple_info) == len(self.multiple_request_pending):
                        # Все данные собраны, отправляем сигнал с полным списком
                        channels = [self.multiple_info[name] for name in self.multiple_request_pending]
                        self.channel_info_updated.emit({'multiple': True, 'channels': channels})
                        self.logger.debug(f"Обновлена информация о {len(channels)} каналах")

                        # Сбрасываем состояние множественного запроса
                        self.multiple_request_pending = None
                        self.multiple_info = {}
                    # Не отправляем промежуточные сигналы для одиночных каналов в множественном запросе
                else:
                    # Одиночный канал
                    self.channel_info_updated.emit(info)
                    self.logger.debug(f"Обновлена информация о канале {channel_name}")

        except Exception as e:
            self.logger.error(f"Ошибка обработки информации о канале: {str(e)}")

    def _handle_channel_history(self, msg_dict):
        """Обработка ответа с историческими данными канала"""
        try:
            # Определяем имя канала из ответа
            channel_name = msg_dict.get('name', '')
            duration = msg_dict.get('duration', '300')

            if channel_name:
                # Добавляем имя канала в ответ
                history_data = msg_dict.copy()
                history_data['name'] = channel_name

                # Разбираем timestamps и values в списки
                timestamps_str = msg_dict.get('timestamps', '')
                values_str = msg_dict.get('values', '')

                if timestamps_str and values_str:
                    history_data['timestamps'] = timestamps_str.split(',')
                    history_data['values'] = values_str.split(',')
                else:
                    history_data['timestamps'] = []
                    history_data['values'] = []

                # Сохраняем в кэш
                cache_key = f"{channel_name}_{duration}"
                self.channel_history_cache[cache_key] = history_data

                # Отправляем сигнал обновления
                self.channel_history_updated.emit(history_data)
                self.logger.debug(f"Обновлена история канала {channel_name} за {duration} секунд")

        except Exception as e:
            self.logger.error(f"Ошибка обработки истории канала: {str(e)}")

    def disconnect_from_server(self):
        """Отключение от VCAS сервера"""
        try:
            if self.update_timer.isActive():
                self.update_timer.stop()

            if self.socket:
                self.socket.close()
                self.socket = None

            self.is_connected = False
            self.disconnected.emit()
            self.logger.info("Отключено от VCAS сервера")

        except Exception as e:
            self.logger.error(f"Ошибка при отключении: {str(e)}")

    def _update_channels(self):
        """Периодическое обновление списка каналов"""
        if self.is_connected:
            try:
                self._send_command('ChannelsList', 'get')
            except Exception as e:
                self.logger.error(f"Ошибка обновления списка каналов: {str(e)}")

    def _channels_changed(self, new_channels):
        """Проверить, изменился ли список каналов"""
        if len(self.channels_list) != len(new_channels):
            return True
        # Сравниваем отсортированные списки для учета порядка
        return sorted(self.channels_list) != sorted(new_channels)

    def _send_command(self, channel_name, method, **kwargs):
        """Отправка команды на сервер"""
        if not self.is_connected or not self.socket:
            return

        try:
            # Формируем команду в формате VCAS протокола
            parts = [f"name:{channel_name}", f"method:{method}"]

            # Добавляем дополнительные параметры
            for key, value in kwargs.items():
                parts.append(f"{key}:{value}")

            # Формируем полную команду
            command = '|'.join(parts) + '\n'

            # Отправляем команду
            self.socket.write(command.encode('utf-8'))
            self.logger.debug(f"Отправлена команда: {command.strip()}")

        except Exception as e:
            self.logger.error(f"Ошибка отправки команды: {str(e)}")

    def get_channels_list(self):
        """Получить список каналов с сервера"""
        if not self.is_connected:
            return []

        try:
            self._send_command('ChannelsList', 'get')
            return self.channels_list
        except Exception as e:
            error_msg = f"Ошибка получения списка каналов: {str(e)}"
            self.logger.error(error_msg)
            self.error.emit(error_msg)
            return []

    def get_channel_info(self, channel_name):
        """Получить детальную информацию о канале"""
        if not self.is_connected or not channel_name:
            return {}

        try:
            # Проверяем кэш сначала
            if channel_name in self.channel_info_cache:
                cached_info = self.channel_info_cache[channel_name]
                self.channel_info_updated.emit(cached_info)
                return cached_info

            # Отправляем запрос на получение полной информации
            self._send_command(channel_name, 'getfull')

        except Exception as e:
            error_msg = f"Ошибка получения информации о канале {channel_name}: {str(e)}"
            self.logger.error(error_msg)
            self.error.emit(error_msg)

        return {}

    def get_channel_history(self, channel_name, duration_seconds=300):
        """Получить исторические данные канала"""
        if not self.is_connected or not channel_name:
            return {}

        try:
            # Проверяем кэш сначала
            cache_key = f"{channel_name}_{duration_seconds}"
            if cache_key in self.channel_history_cache:
                cached_data = self.channel_history_cache[cache_key]
                self.channel_history_updated.emit(cached_data)
                return cached_data

            # Отправляем запрос на получение исторических данных
            # Предполагаем, что сервер поддерживает метод 'gethistory' с параметрами duration
            self._send_command(channel_name, 'gethistory', duration=str(duration_seconds))

            # Подписываемся на обновления канала для получения новых точек
            self._send_command(channel_name, 'subscribe')

        except Exception as e:
            error_msg = f"Ошибка получения истории канала {channel_name}: {str(e)}"
            self.logger.error(error_msg)
            self.error.emit(error_msg)

        return {}

    def refresh_channels(self):
        """Принудительное обновление списка каналов"""
        if self.is_connected:
            self._update_channels()

    def clear_cache(self):
        """Очистить кэш информации о каналах"""
        self.channel_info_cache.clear()
        self.channel_history_cache.clear()
        self.channels_list.clear()
        self.multiple_request_pending = None
        self.multiple_info = {}
        self.logger.info("Кэш каналов очищен")

    def force_refresh_channels(self):
        """Принудительное обновление списка каналов с очисткой кэша"""
        self.clear_cache()
        if self.is_connected:
            self._update_channels()

    def get_multiple_channel_info(self, channels_list):
        """Получить информацию о нескольких каналах"""
        if not self.is_connected or not channels_list:
            return {}

        try:
            # Если только один канал, используем одиночный режим
            if len(channels_list) == 1:
                self.get_channel_info(channels_list[0])
                return {}

            # Сначала проверяем кэш для всех каналов
            cached_channels = []
            missing_channels = []

            for channel_name in channels_list:
                if channel_name in self.channel_info_cache:
                    cached_channels.append(self.channel_info_cache[channel_name])
                else:
                    missing_channels.append(channel_name)

            # Если все каналы в кэше, сразу отправляем сигнал
            if not missing_channels:
                self.channel_info_updated.emit({'multiple': True, 'channels': cached_channels})
                self.logger.debug(f"Все {len(channels_list)} каналов найдены в кэше")
                return cached_channels

            # Если есть недостающие, отправляем запросы и устанавливаем множественный режим
            self.multiple_request_pending = channels_list
            self.multiple_info = {name: info for name, info in self.channel_info_cache.items() if name in channels_list}

            for channel_name in missing_channels:
                self._send_command(channel_name, 'getfull')

        except Exception as e:
            error_msg = f"Ошибка получения информации о каналах {channels_list}: {str(e)}"
            self.logger.error(error_msg)
            self.error.emit(error_msg)

        return {}
