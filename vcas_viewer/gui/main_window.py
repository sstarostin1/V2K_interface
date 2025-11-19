# -*- coding: utf-8 -*-
"""
Главное окно приложения VCAS Viewer с объединенной функциональностью
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QTreeWidget, QTreeWidgetItem, QTextEdit,
                             QStatusBar, QMenuBar, QToolBar, QAction, QLabel,
                             QMessageBox, QApplication, QPushButton, QDockWidget,
                             QStackedWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QItemSelectionModel, QTimer
from PyQt5.QtGui import QIcon, QFont

import sys
import os
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from vcas_viewer.core.vcas_client import VCASClient
from vcas_viewer.core.config import Config
from vcas_viewer.core.mock_vcas_server import MockVCASServer
from vcas_viewer.plotting.plot_manager import PlotManager
from vcas_viewer.gui.widgets.channel_tree_widget import ChannelTreeWidget
from vcas_viewer.gui.widgets.channel_info_widget import ChannelInfoWidget
from vcas_viewer.gui.widgets.navigation_handler import NavigationHandler

import logging


class MainWindow(QMainWindow):
    """Главное окно приложения с древовидным представлением и системой графиков"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('MainWindow')

        # Компоненты
        self.vcas_client = None
        self.plot_manager = None
        self.channel_info_widget = None
        self.current_selected_channel = None  # Текущий выбранный канал для фиксации информации
        self.graph_windows = []  # Список открытых окон графиков

        # Режим правой панели
        self.right_panel_mode = "info"  # "info" или "management"
        self.plot_windows_manager = None  # Виджет управления окнами графиков

        # Mock сервер
        self.mock_server = None
        self.mock_server_thread = None

        # Флаг автоматической попытки подключения
        self.auto_connect_attempted = False

        # Таймеры
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._check_connection_status)

        # Таймер автоматического подключения
        self.auto_connect_timer = QTimer()
        self.auto_connect_timer.setSingleShot(True)
        self.auto_connect_timer.timeout.connect(self._auto_connect_timeout)
        self.logger.debug("Автоматический таймер подключения настроен на 0.5 секунды")

        self.setup_logging()
        self.setup_ui()
        self.setup_vcas_client()
        self.setup_plot_manager()
        self.setup_plot_windows_manager()
        self.setup_connections()

        # Автоматическое подключение через 0.5 секунды после запуска
        self.logger.info("Выполняется автоматическое подключение к VCAS серверу через 0.5 секунды")
        self.auto_connect_timer.start(500)

    def setup_logging(self):
        """Настройка логирования - теперь глобальная, оставлено для совместимости"""
        # Логирование настроено глобально через logging_config.configure_logging()
        # Этот метод оставлен для поддержания API MainWindow
        pass

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle(Config.WINDOW_TITLE)
        width, height = Config.get_window_size()
        self.setGeometry(100, 100, width, height)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        main_layout = QHBoxLayout(central_widget)

        # Создаем splitter для разделения дерева каналов и области информации/графиков
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Левая панель - дерево каналов
        self.channel_tree = ChannelTreeWidget(self)
        self.main_splitter.addWidget(self.channel_tree)

        # Правая панель - информация и графики
        self.setup_right_panel()

        # Настройка меню и панели инструментов
        self.setup_menu_bar()
        self.setup_tool_bar()
        self.setup_status_bar()

        # Настройка навигации
        self.navigation_handler = NavigationHandler(self.channel_tree)

        # Загружаем конфигурацию
        Config.load_config()
        self._apply_config()

    def setup_right_panel(self):
        """Настройка правой панели с информацией и графиками"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        # Создаем stacked widget для переключения режимов
        self.right_panel_stack = QStackedWidget()

        # Режим информации о каналах
        self.setup_info_mode_widget()

        # Режим управления окнами графиков
        self.setup_management_mode_widget()

        right_layout.addWidget(self.right_panel_stack)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setSizes([300, 400, 400])  # Начальные размеры

    def setup_info_mode_widget(self):
        """Настройка виджета режима информации"""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        # Верхняя часть - информация о канале
        self.channel_info_widget = ChannelInfoWidget()
        info_layout.addWidget(self.channel_info_widget)

        # Нижняя часть - область графиков (изначально пустая)
        self.graph_area = QWidget()
        graph_layout = QVBoxLayout(self.graph_area)
        graph_layout.addWidget(QWidget())  # Пустой виджет-заполнитель
        info_layout.addWidget(self.graph_area)

        self.right_panel_stack.addWidget(info_widget)

    def setup_management_mode_widget(self):
        """Настройка виджета режима управления окнами"""
        # Виджет управления окнами добавляется в стек в setup_plot_windows_manager
        pass

    def _apply_config(self):
        """Применить настройки конфигурации"""
        # Восстанавливаем раскрытые директории
        self._restore_expanded_dirs()

    def _restore_expanded_dirs(self):
        """Восстановить раскрытые директории из конфигурации"""
        if not Config.EXPANDED_DIRS:
            return

        def expand_items(parent, path_parts):
            if not path_parts:
                return
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.text(0) == path_parts[0] and child.childCount() > 0:
                    child.setExpanded(True)
                    if len(path_parts) > 1:
                        expand_items(child, path_parts[1:])

        for dir_path in Config.EXPANDED_DIRS:
            parts = dir_path.split('/')
            expand_items(self.channel_tree.invisibleRootItem(), parts)

    def keyPressEvent(self, event):
        """Обработчик нажатий клавиш"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Проверяем, находится ли фокус в поле редактирования названия в виджете управления окнами
            if self.plot_windows_manager and self.plot_windows_manager.has_focus_in_title_edit:
                # Фокус в поле редактирования названия - не перехватываем Enter, позволяем обработать inline-редактирование
                event.ignore()
                return

            # Обработка нажатия Enter для открытия графиков
            selected_channels = [item.data(0, Qt.UserRole) for item in self.channel_tree.selected_items if item.data(0, Qt.UserRole)]
            if selected_channels:
                self.logger.debug(f"Нажата клавиша Enter для открытия графиков с {len(selected_channels)} каналами: {selected_channels[:3]}...")
                self.open_plot_window(selected_channels)
                event.accept()
                return

        if self.navigation_handler.handle_key(event):
            self.logger.debug("Обработан клавиатурный ввод с помощью NavigationHandler")
            event.accept()
            self.update_focus_from_current_item()
        else:
            super().keyPressEvent(event)

    def update_focus_from_current_item(self):
        """Обновить фокус в таблице на основе текущего элемента в дереве"""
        current = self.channel_tree.currentItem()
        if current:
            channel_name = current.data(0, Qt.UserRole)
            if channel_name:
                # Это канал - обновляем информацию
                self.on_channel_selected(channel_name)
            else:
                # Это директория - обновляем статистику
                self.on_directory_selected(current.text(0))

    def setup_menu_bar(self):
        """Настройка меню"""
        menubar = self.menuBar()

        # Меню Файл
        file_menu = menubar.addMenu('Файл')

        connect_action = QAction('Подключиться', self)
        connect_action.triggered.connect(self.connect_to_server)
        file_menu.addAction(connect_action)

        disconnect_action = QAction('Отключиться', self)
        disconnect_action.triggered.connect(self.disconnect_from_server)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        exit_action = QAction('Выход', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Меню Сервис
        tools_menu = menubar.addMenu('Сервис')

        refresh_action = QAction('Обновить каналы', self)
        refresh_action.triggered.connect(self.refresh_channels)
        tools_menu.addAction(refresh_action)

        clear_cache_action = QAction('Очистить кэш', self)
        clear_cache_action.triggered.connect(self.clear_cache)
        tools_menu.addAction(clear_cache_action)

        force_refresh_action = QAction('Принудительное обновление', self)
        force_refresh_action.triggered.connect(self.force_refresh_channels)
        tools_menu.addAction(force_refresh_action)

        # Меню Вид
        view_menu = menubar.addMenu('Вид')

        create_plot_action = QAction('Создать окно графиков', self)
        create_plot_action.triggered.connect(self.create_plot_window)
        view_menu.addAction(create_plot_action)

        # Меню Справка
        help_menu = menubar.addMenu('Справка')

        about_action = QAction('О программе', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_tool_bar(self):
        """Настройка панели инструментов"""
        toolbar = self.addToolBar('Основные')

        connect_action = QAction('Подключиться', self)
        connect_action.triggered.connect(self.connect_to_server)
        toolbar.addAction(connect_action)

        disconnect_action = QAction('Отключиться', self)
        disconnect_action.triggered.connect(self.disconnect_from_server)
        toolbar.addAction(disconnect_action)

        toolbar.addSeparator()

        refresh_action = QAction('Обновить', self)
        refresh_action.triggered.connect(self.refresh_channels)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        toggle_panel_action = QAction('Графики', self)
        toggle_panel_action.triggered.connect(self.toggle_right_panel_mode)
        toolbar.addAction(toggle_panel_action)

    def setup_status_bar(self):
        """Настройка статус-бара"""
        self.status_bar = self.statusBar()

        # Индикатор режима работы
        if Config.is_mock_mode():
            mode_text = "Режим: Тестовый сервер"
        else:
            mode_text = "Режим: Реальный сервер"
        self.mode_label = QLabel(mode_text)
        self.status_bar.addWidget(self.mode_label)

        # Индикатор подключения
        self.connection_label = QLabel("Отключено")
        self.status_bar.addWidget(self.connection_label)

        # Информация о каналах
        self.channels_label = QLabel("Каналов: 0")
        self.status_bar.addPermanentWidget(self.channels_label)

    def setup_vcas_client(self):
        """Настройка VCAS клиента"""
        host, port = Config.get_vcas_address()
        self.vcas_client = VCASClient(host, port)
        self.start_mock_server()

    def start_mock_server(self):
        """Запуск mock сервера в отдельном потоке"""
        if not Config.is_mock_mode():
            return

        def run_server():
            self.mock_server = MockVCASServer("127.0.0.1", 20042)
            if self.mock_server.start():
                self.logger.info("Mock VCAS сервер запущен на 127.0.0.1:20042")
            else:
                self.logger.error("Не удалось запустить mock сервер")

        self.mock_server_thread = threading.Thread(target=run_server, daemon=True)
        self.mock_server_thread.start()

    def setup_plot_manager(self):
        """Настройка менеджера графиков"""
        self.plot_manager = PlotManager(self.vcas_client)
        self.logger.info("Менеджер графиков создан")

    def setup_plot_windows_manager(self):
        """Настройка виджета управления окнами графиков"""
        from vcas_viewer.gui.widgets.plot_windows_manager_widget import PlotWindowsManagerWidget
        self.plot_windows_manager = PlotWindowsManagerWidget(self.plot_manager)
        self.plot_windows_manager.create_window_requested.connect(self.create_plot_window)
        self.plot_windows_manager.window_loaded.connect(self._on_window_loaded)

        # Добавляем виджет управления в стек правой панели
        self.right_panel_stack.addWidget(self.plot_windows_manager)

        self.logger.info("Виджет управления окнами графиков создан")

    def setup_connections(self):
        """Настройка соединений сигналов"""
        if self.vcas_client:
            self.vcas_client.connected.connect(self.on_connected)
            self.vcas_client.disconnected.connect(self.on_disconnected)
            self.vcas_client.error.connect(self.on_error)
            self.vcas_client.channels_updated.connect(self.on_channels_updated)
            self.vcas_client.channel_info_updated.connect(self.on_channel_info_updated)

        # Менеджер графиков
        self.plot_manager.plot_window_created.connect(self._on_plot_window_created)
        self.plot_manager.plot_window_closed.connect(self._on_plot_window_closed)
        self.plot_manager.channel_data_updated.connect(self._on_channel_data_updated)

        # Дерево каналов
        self.channel_tree.channel_selected.connect(self.on_channel_selected)
        self.channel_tree.directory_selected.connect(self.on_directory_selected)
        self.channel_tree.multiple_selected.connect(self.on_multiple_selected)
        self.channel_tree.channels_dragged.connect(self.on_channels_dragged)

    def connect_to_server(self):
        """Подключение к VCAS серверу"""
        if self.vcas_client:
            host, port = Config.get_vcas_address()
            mode_text = "тестовому" if Config.is_mock_mode() else "реальному"
            self.update_status(f"Подключение к {mode_text} серверу {host}:{port}...")
            self.logger.info(f"Подключение к {mode_text} серверу {host}:{port}")
            self.auto_connect_attempted = True
            self.vcas_client.connect_to_server()

    def disconnect_from_server(self):
        """Отключение от VCAS сервера"""
        if self.vcas_client:
            self.vcas_client.disconnect_from_server()

    def refresh_channels(self):
        """Обновить список каналов"""
        if self.vcas_client and self.vcas_client.is_connected:
            self.update_status("Обновление каналов...")
            self.vcas_client.refresh_channels()

    def clear_cache(self):
        """Очистить кэш"""
        if self.vcas_client:
            self.vcas_client.clear_cache()

    def force_refresh_channels(self):
        """Принудительное обновление с очисткой кэша"""
        if self.vcas_client:
            self.update_status("Принудительное обновление каналов...")
            self.vcas_client.force_refresh_channels()

    def on_connected(self):
        """Обработчик успешного подключения"""
        self.update_status("Подключено к VCAS серверу")
        self.connection_label.setText("Подключено")
        self.auto_connect_attempted = False

        # Получаем список каналов после подключения
        if self.vcas_client:
            self.vcas_client.get_channels_list()

    def on_disconnected(self):
        """Обработчик отключения"""
        self.update_status("Отключено от сервера")
        self.connection_label.setText("Отключено")
        self.channel_tree.clear()

        # Если это была автоматическая попытка подключения, показать предупреждение
        if self.auto_connect_attempted:
            QMessageBox.warning(self, "Ошибка подключения",
                               "Не удалось автоматически подключиться к серверу VCAS.\n"
                               "Проверьте доступность сервера и повторите попытку вручную.")
            self.auto_connect_attempted = False

    def on_error(self, error_msg):
        """Обработчик ошибок"""
        self.update_status(f"Ошибка: {error_msg}")
        QMessageBox.warning(self, "Ошибка VCAS", error_msg)
        self.auto_connect_attempted = False

    def on_channels_updated(self, channels):
        """Обработчик обновления списка каналов"""
        self.logger.info(f"MainWindow: получен сигнал обновления каналов с {len(channels)} каналами")
        self.channel_tree.update_channels(channels)
        self.channels_label.setText(f"Каналов: {len(channels)}")
        self.update_status(f"Загружено каналов: {len(channels)}")

    def on_channel_selected(self, channel_name):
        """Обработчик выбора канала в дереве"""
        self.current_selected_channel = channel_name  # Фиксируем выбранный канал
        if self.vcas_client and self.vcas_client.is_connected:
            self.update_status(f"Получение информации о канале: {channel_name}")
            self.vcas_client.get_channel_info(channel_name)

    def on_directory_selected(self, directory_name):
        """Обработчик выбора директории в дереве"""
        self.update_status(f"Выбрана директория: {directory_name}")

    def on_multiple_selected(self, selected_channels):
        """Обработчик множественного выбора каналов"""
        if selected_channels and self.vcas_client and self.vcas_client.is_connected:
            self.update_status(f"Получение информации о {len(selected_channels)} каналах...")
            # Если один канал, используем одиночный запрос
            if len(selected_channels) == 1:
                self.vcas_client.get_channel_info(selected_channels[0])
            else:
                self.vcas_client.get_multiple_channel_info(selected_channels)

    def on_channel_info_updated(self, info):
        """Обработчик обновления информации о канале"""
        if info and self.channel_info_widget:
            if info.get('multiple'):
                # Множественный выбор каналов
                channels = info['channels']
                self.update_status(f"Информация о {len(channels)} каналах обновлена")
            else:
                # Одиночный канал - обновляем только если это текущий выбранный канал
                if info.get('name') and info['name'] == self.current_selected_channel:
                    self.update_status(f"Информация о канале {info['name']} обновлена")
                    self.channel_info_widget.update_channel_info(info)

    def on_channels_dragged(self, channel_names):
        """Обработчик перетаскивания каналов"""
        self.logger.info(f"Перетаскивание каналов: {channel_names}")

        # Создаем окно графиков если его нет
        if self.plot_manager.get_window_count() == 0:
            self.create_plot_window()

        # Добавляем каналы в первое окно
        plot_windows = list(self.plot_manager.plot_windows.values())
        if plot_windows:
            plot_window = plot_windows[0]
            for channel_name in channel_names:
                self.plot_manager.add_channel_to_window(channel_name, plot_window)

    def create_plot_window(self):
        """Создать новое окно графиков"""
        plot_window = self.plot_manager.create_plot_window("Графики каналов")

        if plot_window:
            # Добавляем окно как доковое
            self.addDockWidget(Qt.RightDockWidgetArea, plot_window)

            self.logger.info("Создано новое окно графиков")

    def open_plot_window(self, channels_list):
        """Открыть окно графиков для выбранных каналов"""
        if not channels_list:
            return

        self.logger.info(f"Открытие окна графиков для каналов: {channels_list}")

        # Создаем окно графиков
        plot_window = self.plot_manager.create_plot_window("Графики каналов")

        if plot_window:
            # Добавляем окно как доковое
            self.addDockWidget(Qt.RightDockWidgetArea, plot_window)

            # Добавляем каналы в окно
            for channel_name in channels_list:
                self.plot_manager.add_channel_to_window(channel_name, plot_window)

            self.update_status(f"Открыто окно графиков для {len(channels_list)} каналов")

    def _on_plot_window_created(self, plot_window):
        """Обработчик создания окна графиков"""
        self.logger.info("Создано окно графиков")

    def _on_plot_window_closed(self, plot_window):
        """Обработчик закрытия окна графиков"""
        self.logger.info("Закрыто окно графиков")

    def _on_channel_data_updated(self, channel_name, channel_data):
        """Обработчик обновления данных канала"""
        # Обновляем данные в окнах графиков
        for plot_window in self.plot_manager.plot_windows.values():
            plot_window.update_channel_data(channel_name, channel_data)

    def _on_window_loaded(self, plot_window):
        """Обработчик загрузки окна из конфигурации"""
        if plot_window:
            # Добавляем загруженное окно как dock widget
            self.addDockWidget(Qt.RightDockWidgetArea, plot_window)
            self.logger.info("Загруженное окно добавлено как dock widget")

    def toggle_right_panel_mode(self):
        """Переключение режима правой панели"""
        if self.right_panel_mode == "info":
            self.switch_to_management_mode()
        else:
            self.switch_to_info_mode()

    def switch_to_info_mode(self):
        """Переключение в режим информации о каналах"""
        self.right_panel_mode = "info"
        self.right_panel_stack.setCurrentIndex(0)  # Первый виджет - режим информации
        self.logger.info("Переключено в режим информации о каналах")

    def switch_to_management_mode(self):
        """Переключение в режим управления окнами графиков"""
        self.right_panel_mode = "management"
        self.right_panel_stack.setCurrentIndex(1)  # Второй виджет - режим управления
        self.logger.info("Переключено в режим управления окнами графиков")

    def update_status(self, message):
        """Обновить сообщение в статусбаре"""
        self.status_bar.showMessage(message, 5000)

    def _auto_connect_timeout(self):
        """Обработчик таймера автоматического подключения"""
        self.logger.info("Таймер автоматического подключения истек, пытаемся подключиться")
        self.connect_to_server()

    def show_about(self):
        """Показать информацию о программе"""
        self.logger.info("Открыт диалог 'О программе'")
        QMessageBox.about(
            self,
            "О программе",
            f"{Config.WINDOW_TITLE}\n\n"
            "Программа для просмотра архитектуры VCAS сервера\n"
            "Разработано для ВЭПП-2000\n\n"
            "Версия 1.0"
        )

    def _check_connection_status(self):
        """Проверка статуса подключения"""
        if self.vcas_client and not self.vcas_client.is_connected:
            self.connection_label.setText("Подключение...")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        # Сохраняем конфигурацию перед закрытием
        Config.save_config()
        if self.vcas_client:
            self.vcas_client.disconnect_from_server()
        if self.mock_server:
            self.mock_server.stop()
            self.logger.info("Mock сервер остановлен")
        if self.plot_manager:
            self.plot_manager.clear_all_data()
        event.accept()
