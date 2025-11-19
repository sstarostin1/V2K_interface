# -*- coding: utf-8 -*-
"""
Диалог переименования окна графика
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QDialogButtonBox)
from PyQt5.QtCore import Qt
import logging


class RenameWindowDialog(QDialog):
    """Диалог для переименования окна графика"""

    def __init__(self, current_name: str, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger('RenameWindowDialog')
        self.logger.debug(f"Создан диалог переименования окна '{current_name}'")
        self.current_name = current_name
        self.new_name = current_name

        self.setup_ui()
        self.setup_connections()

    def setup_ui(self):
        """Настройка интерфейса"""
        self.setWindowTitle("Переименование окна графика")
        self.setModal(True)
        self.setFixedSize(300, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Метка
        label = QLabel("Введите новое название окна:")
        layout.addWidget(label)

        # Поле ввода
        self.name_edit = QLineEdit(self.current_name)
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        layout.addWidget(self.name_edit)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def setup_connections(self):
        """Настройка соединений"""
        self.name_edit.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str):
        """Обработчик изменения текста"""
        self.new_name = text.strip()

    def get_new_name(self) -> str:
        """Получение введенного названия"""
        return self.new_name

    @staticmethod
    def get_name(current_name: str, parent=None) -> str:
        """Статический метод для получения нового названия"""
        dialog = RenameWindowDialog(current_name, parent)
        result = dialog.exec_()

        if result == QDialog.Accepted:
            return dialog.get_new_name()
        else:
            return current_name
