# -*- coding: utf-8 -*-
"""
Виджет для отображения информации о канале
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit
from PyQt5.QtGui import QFont


class ChannelInfoWidget(QWidget):
    """Виджет для отображения информации о канале"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)

        # Заголовок
        title_label = QLabel("Информация о канале")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Текстовое поле для информации
        self.info_text = QTextEdit()
        self.info_text.setFont(QFont("Consolas", 9))
        self.info_text.setMaximumHeight(200)
        layout.addWidget(self.info_text)

        # Поле для описания канала
        desc_label = QLabel("Описание:")
        layout.addWidget(desc_label)

        self.desc_text = QTextEdit()
        self.desc_text.setFont(QFont("Consolas", 8))
        self.desc_text.setMaximumHeight(100)
        layout.addWidget(self.desc_text)

        layout.addStretch()

    def update_channel_info(self, info):
        """Обновить информацию о канале"""
        if not info:
            self.info_text.clear()
            self.desc_text.clear()
            return

        # Форматируем основную информацию
        info_lines = []
        for key, value in info.items():
            if key not in ['descr']:  # Описание показываем отдельно
                info_lines.append(f"{key}: {value}")

        self.info_text.setPlainText('\n'.join(info_lines))

        # Показываем описание
        self.desc_text.setPlainText(info.get('descr', 'Описание отсутствует'))
