# -*- coding: utf-8 -*-
"""
Виджет управления окнами графиков
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QMessageBox, QAbstractItemView, QLineEdit, QComboBox, QFileDialog, QDialog, QListWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from vcas_viewer.plotting.plot_manager import PlotManager
from .rename_window_dialog import RenameWindowDialog


class PlotWindowsManagerWidget(QWidget):
    """
    Виджет для управления окнами графиков
    """

    # Сигналы
    create_window_requested = pyqtSignal()  # Запрос создания нового окна
    window_loaded = pyqtSignal(object)  # Окно загружено из конфигурации

    def __init__(self, plot_manager: PlotManager, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('PlotWindowsManagerWidget')
        self.plot_manager = plot_manager

        # Флаг отслеживания фокуса в поле редактирования названия
        self.has_focus_in_title_edit = False

        self.setup_ui()
        self.setup_connections()
        self.update_windows_list()

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Заголовок
        title_label = QLabel("Управление окнами графиков")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        # Список окон
        self.windows_list = QListWidget()
        self.windows_list.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Отключаем встроенное редактирование
        self.windows_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
            }
        """)
        layout.addWidget(self.windows_list)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        # Кнопка создания нового окна
        self.create_button = QPushButton("Создать новое окно")
        self.create_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        buttons_layout.addWidget(self.create_button)

        # Кнопка загрузки конфигурации
        self.load_config_button = QPushButton("📁 Загрузить конфигурацию")
        self.load_config_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e24aa;
            }
            QPushButton:pressed {
                background-color: #7b1fa2;
            }
        """)
        self.load_config_button.setToolTip("Загрузить сохраненную конфигурацию окна")
        buttons_layout.addWidget(self.load_config_button)

        # Растягивающий элемент
        buttons_layout.addStretch()

        layout.addLayout(buttons_layout)

        # Растягивающий элемент
        layout.addStretch()

    def setup_connections(self):
        """Настройка соединений сигналов"""
        self.create_button.clicked.connect(self._on_create_button_clicked)
        self.load_config_button.clicked.connect(self._on_load_config_button_clicked)

        # Подключаемся к сигналам PlotManager
        if self.plot_manager:
            self.plot_manager.plot_window_created.connect(self._on_window_created)
            self.plot_manager.plot_window_closed.connect(self._on_window_closed)
            self.plot_manager.plot_window_settings_changed.connect(self._on_window_settings_changed)
            self.plot_manager.channels_changed.connect(self._on_channels_changed)

    def update_windows_list(self):
        """Обновление списка окон"""
        # Явно очищаем виджеты перед очисткой списка
        for i in range(self.windows_list.count()):
            item = self.windows_list.item(i)
            if item:
                self.windows_list.setItemWidget(item, None)

        self.windows_list.clear()

        if not self.plot_manager:
            return

        windows_info = self.plot_manager.get_all_windows_info()

        for window_info in windows_info:
            self._add_window_item(window_info)

        self.logger.debug(f"Обновлен список окон: {len(windows_info)} окон")

    def _add_window_item(self, window_info: dict):
        """
        Добавить элемент окна в список с многострочным интерфейсом

        Args:
            window_info: Информация об окне
        """
        window_id = window_info['window_id']
        title = window_info['title']
        channels = window_info['channels']
        time_window = window_info['time_window']

        # Создаем элемент списка
        item = QListWidgetItem("")
        item.setData(Qt.UserRole, window_id)

        # Создаем многострочный виджет
        item_widget = self._create_window_item_widget(window_info)

        # Устанавливаем размер элемента
        item.setSizeHint(item_widget.sizeHint())

        # Добавляем элемент в список
        self.windows_list.addItem(item)
        self.windows_list.setItemWidget(item, item_widget)

    def _create_window_item_widget(self, window_info: dict) -> QWidget:
        """
        Создать многострочный виджет для элемента окна

        Args:
            window_info: Информация об окне

        Returns:
            Виджет элемента окна
        """
        window_id = window_info['window_id']
        title = window_info['title']
        channels = window_info['channels']

        # Основной виджет
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)

        # Строка 1: Название с inline-редактированием
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(5)

        title_label = QLabel("Название:")
        title_label.setFixedWidth(60)
        title_label.setStyleSheet("font-weight: bold; color: #555;")
        title_layout.addWidget(title_label)

        title_edit = QLineEdit(title)
        title_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 5px;
                background-color: white;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """)
        title_edit.editingFinished.connect(lambda: self._on_title_edit_finished(title_edit, window_id))
        title_edit.focusInEvent = lambda event: self._on_title_edit_focus_in(event)
        title_edit.focusOutEvent = lambda event, te=title_edit, wid=window_id: self._on_title_edit_focus_out(event, te, title, wid)
        title_layout.addWidget(title_edit)

        layout.addLayout(title_layout)

        # Строка 2: Каналы в раскрывающемся списке
        channels_layout = QHBoxLayout()
        channels_layout.setContentsMargins(0, 0, 0, 0)
        channels_layout.setSpacing(5)

        channels_label = QLabel("Каналы:")
        channels_label.setFixedWidth(60)
        channels_label.setStyleSheet("font-weight: bold; color: #555;")
        channels_layout.addWidget(channels_label)

        channels_combo = QComboBox()
        channels_combo.setMaxVisibleItems(10)
        channels_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px 5px;
                background-color: white;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)

        # Добавляем каналы в список
        if channels:
            for channel in channels:
                channels_combo.addItem(channel)
            channels_combo.setCurrentIndex(0)
        else:
            channels_combo.addItem("Нет каналов")
            channels_combo.setEnabled(False)

        channels_layout.addWidget(channels_combo)
        layout.addLayout(channels_layout)

        # Строка 3: Функциональные кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(5)

        # Растягивающий элемент для выравнивания кнопок вправо
        buttons_layout.addStretch()

        # Кнопка сохранения конфигурации
        save_config_button = QPushButton("💾 Конфиг")
        save_config_button.setToolTip("Сохранить конфигурацию окна")
        save_config_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        save_config_button.clicked.connect(lambda: self._save_window_config(window_id))
        buttons_layout.addWidget(save_config_button)

        # Кнопка сохранения данных
        save_data_button = QPushButton("📊 Данные")
        save_data_button.setToolTip("Сохранить данные каналов в CSV")
        save_data_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        save_data_button.clicked.connect(lambda: self._save_window_data(window_id))
        buttons_layout.addWidget(save_data_button)

        # Кнопка скриншота
        screenshot_button = QPushButton("📸 Скриншот")
        screenshot_button.setToolTip("Создать скриншот окна")
        screenshot_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
        """)
        screenshot_button.clicked.connect(lambda: self._save_window_screenshot(window_id))
        buttons_layout.addWidget(screenshot_button)

        # Кнопка удаления окна
        delete_button = QPushButton("🗑️ Удалить")
        delete_button.setToolTip("Закрыть окно графиков")
        delete_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        delete_button.clicked.connect(lambda: self._close_window(window_id))
        buttons_layout.addWidget(delete_button)

        layout.addLayout(buttons_layout)

        return widget

    def _on_create_button_clicked(self):
        """Обработчик нажатия кнопки создания окна"""
        self.create_window_requested.emit()

    def _rename_window(self, window_id: str):
        """
        Переименовать окно

        Args:
            window_id: ID окна
        """
        if not self.plot_manager:
            return

        # Получаем текущую информацию об окне
        window_info = self.plot_manager.get_window_info(window_id)
        if not window_info:
            return

        current_title = window_info['title']

        # Показываем диалог переименования
        new_title = RenameWindowDialog.get_name(current_title, self)
        if new_title and new_title != current_title:
            self.plot_manager.rename_window(window_id, new_title)
            self.update_windows_list()

    def _close_window(self, window_id: str):
        """
        Закрыть окно

        Args:
            window_id: ID окна
        """
        if not self.plot_manager:
            return

        # Подтверждение закрытия
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы действительно хотите закрыть это окно графиков?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Находим окно и закрываем его
            if window_id in self.plot_manager.plot_windows:
                plot_window = self.plot_manager.plot_windows[window_id]
                self.plot_manager.close_plot_window(plot_window)

    def _on_window_created(self, plot_window):
        """Обработчик создания окна"""
        self.update_windows_list()

    def _on_window_closed(self, plot_window):
        """Обработчик закрытия окна"""
        self.update_windows_list()

    def _on_window_settings_changed(self, plot_window):
        """Обработчик изменения настроек окна"""
        self.update_windows_list()

    def _on_channels_changed(self, window_id: str):
        """Обработчик изменения каналов в окне"""
        self.update_windows_list()

    def _validate_window_title(self, title: str, exclude_window_id: str = None) -> str:
        """
        Валидация названия окна

        Args:
            title: Название для проверки
            exclude_window_id: ID окна, которое исключается из проверки уникальности

        Returns:
            Сообщение об ошибке или пустая строка при успехе
        """
        if not title or not title.strip():
            return "Название окна не может быть пустым"

        title = title.strip()

        if len(title) > 50:
            return "Название окна не может быть длиннее 50 символов"

        # Проверка на недопустимые символы
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in invalid_chars:
            if char in title:
                return f"Название окна не может содержать символ '{char}'"

        # Проверка уникальности
        if self.plot_manager:
            for window_id, window in self.plot_manager.plot_windows.items():
                if exclude_window_id and window_id == exclude_window_id:
                    continue
                if window.windowTitle() == title:
                    return f"Окно с названием '{title}' уже существует"

        return ""

    def _on_title_edit_finished(self, line_edit: QLineEdit, window_id: str):
        """
        Обработчик завершения редактирования названия (Enter)

        Args:
            line_edit: Поле редактирования
            window_id: ID окна
        """
        new_title = line_edit.text().strip()

        # Валидация названия
        validation_error = self._validate_window_title(new_title, window_id)
        if validation_error:
            QMessageBox.warning(self, "Неверное название", validation_error)
            # Возвращаем оригинальное название
            if self.plot_manager:
                current_info = self.plot_manager.get_window_info(window_id)
                if current_info:
                    line_edit.setText(current_info['title'])
            return

        if new_title and self.plot_manager:
            self.plot_manager.rename_window(window_id, new_title)
            self.update_windows_list()  # Обновляем список визуально
            self.logger.info(f"Название окна {window_id} изменено на '{new_title}'")



    def _on_title_edit_focus_in(self, event):
        """
        Обработчик получения фокуса полем редактирования названия

        Args:
            event: Событие получения фокуса
        """
        self.has_focus_in_title_edit = True

    def _on_title_edit_focus_out(self, event, line_edit: QLineEdit, original_title: str, window_id: str):
        """
        Обработчик потери фокуса полем редактирования названия (откат)

        Args:
            event: Событие потери фокуса
            line_edit: Поле редактирования
            original_title: Оригинальное название
            window_id: ID окна
        """
        self.has_focus_in_title_edit = False

        # Откатываем изменения к оригинальному названию
        line_edit.setText(original_title)

        # Вызываем стандартную обработку события
        QLineEdit.focusOutEvent(line_edit, event)

    def _save_window_config(self, window_id: str):
        """
        Сохранить конфигурацию окна

        Args:
            window_id: ID окна
        """
        if not self.plot_manager:
            return

        filepath = self.plot_manager.save_window_config_to_file(window_id)
        if filepath:
            QMessageBox.information(
                self, "Успех",
                f"Конфигурация окна сохранена:\n{filepath}"
            )
        else:
            QMessageBox.warning(
                self, "Ошибка",
                "Не удалось сохранить конфигурацию окна"
            )

    def _save_window_data(self, window_id: str):
        """
        Сохранить данные окна в CSV

        Args:
            window_id: ID окна
        """
        if not self.plot_manager:
            QMessageBox.warning(self, "Ошибка", "Менеджер графиков не доступен")
            return

        try:
            filepath = self.plot_manager.export_window_data(window_id)
            if filepath:
                QMessageBox.information(
                    self, "Успех",
                    f"Данные окна сохранены:\n{filepath}"
                )
            else:
                # Проверяем возможные причины ошибки
                if window_id not in self.plot_manager.plot_windows:
                    error_msg = f"Окно с ID '{window_id}' не найдено"
                else:
                    window_info = self.plot_manager.get_window_info(window_id)
                    channels = window_info.get('channels', [])
                    if not channels:
                        error_msg = "В окне нет каналов для экспорта данных"
                    else:
                        error_msg = "Не удалось экспортировать данные. Проверьте логи для деталей."

                QMessageBox.warning(self, "Ошибка сохранения данных", error_msg)

        except Exception as e:
            error_msg = f"Произошла ошибка при сохранении данных:\n{str(e)}"
            self.logger.error(f"Ошибка сохранения данных окна {window_id}: {e}")
            QMessageBox.critical(self, "Критическая ошибка", error_msg)

    def _save_window_screenshot(self, window_id: str):
        """
        Создать скриншот окна

        Args:
            window_id: ID окна
        """
        if not self.plot_manager:
            return

        filepath = self.plot_manager.save_window_screenshot(window_id)
        if filepath:
            QMessageBox.information(
                self, "Успех",
                f"Скриншот окна сохранен:\n{filepath}"
            )
        else:
            QMessageBox.warning(
                self, "Ошибка",
                "Не удалось создать скриншот окна"
            )

    def _on_load_config_button_clicked(self):
        """
        Обработчик нажатия кнопки загрузки конфигурации
        """
        if not self.plot_manager:
            QMessageBox.warning(self, "Ошибка", "Менеджер графиков не доступен")
            return

        # Получаем список сохраненных конфигураций
        configs_list = self.plot_manager.get_saved_configs_list()

        if not configs_list:
            QMessageBox.information(
                self, "Информация",
                "Нет сохраненных конфигураций окон.\nСначала сохраните конфигурацию какого-либо окна."
            )
            return

        # Показываем диалог выбора конфигурации
        selected_config = self._show_config_selection_dialog(configs_list)
        if selected_config:
            self._load_selected_config(selected_config)

    def _show_config_selection_dialog(self, configs_list: list) -> dict:
        """
        Показать диалог выбора конфигурации

        Args:
            configs_list: Список доступных конфигураций

        Returns:
            Выбранная конфигурация или None
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Выбор конфигурации окна")
        dialog.setModal(True)
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)

        # Заголовок
        title_label = QLabel("Выберите конфигурацию для загрузки:")
        layout.addWidget(title_label)

        # Список конфигураций
        config_list_widget = QListWidget()
        for config in configs_list:
            item_text = f"{config['title']} - {config['channels_count']} каналов"
            if config['export_timestamp']:
                item_text += f" ({config['export_timestamp']})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, config)
            config_list_widget.addItem(item)
        layout.addWidget(config_list_widget)

        # Кнопки
        buttons_layout = QHBoxLayout()
        load_button = QPushButton("Загрузить")
        load_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(dialog.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(load_button)
        layout.addLayout(buttons_layout)

        # Обработка результата
        if dialog.exec_() == QDialog.Accepted and config_list_widget.currentItem():
            selected_item = config_list_widget.currentItem()
            return selected_item.data(Qt.UserRole)

        return None

    def _load_selected_config(self, config: dict):
        """
        Загрузить выбранную конфигурацию

        Args:
            config: Конфигурация для загрузки
        """
        filepath = config.get('filepath', '')
        if not filepath:
            QMessageBox.warning(self, "Ошибка", "Неверный путь к файлу конфигурации")
            return

        try:
            # Загружаем конфигурацию
            plot_window = self.plot_manager.load_window_config_from_file(filepath)
            if plot_window:
                # Отправляем сигнал о загрузке окна для добавления его как dock widget
                self.window_loaded.emit(plot_window)
                QMessageBox.information(
                    self, "Успех",
                    f"Конфигурация '{config['title']}' успешно загружена.\nСоздано новое окно графиков."
                )
            else:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Не удалось загрузить конфигурацию окна"
                )

        except Exception as e:
            error_msg = f"Ошибка при загрузке конфигурации:\n{str(e)}"
            self.logger.error(f"Ошибка загрузки конфигурации {filepath}: {e}")
            QMessageBox.critical(self, "Критическая ошибка", error_msg)
