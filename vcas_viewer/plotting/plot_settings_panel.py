# -*- coding: utf-8 -*-
"""
PlotSettingsPanel - панель настроек графика с анимацией
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QCheckBox, QFrame, QApplication, QComboBox
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, pyqtSignal, QEvent, QPoint
from PyQt5.QtGui import QPalette, QColor
import logging


class FillMode:
    """
    Режимы заполнения графика
    """
    ROLLING_RIGHT = "rolling_right"  # Скользящий справа (окно вокруг current_time, скользит)
    SWEEPING_LEFT = "sweeping_left"  # Сканирующее слева (чистое сканирование с очисткой)


class PlotSettings:
    """
    Настройки графика
    """
    def __init__(self, time_window_minutes=5, use_system_time=True, fill_mode=FillMode.ROLLING_RIGHT):
        self.time_window_minutes = time_window_minutes
        self.use_system_time = use_system_time
        self.fill_mode = fill_mode


class PlotSettingsPanel(QWidget):
    """
    Панель настроек графика с анимацией появления/исчезновения
    """

    # Сигналы
    settings_changed = pyqtSignal()  # Изменены настройки

    def __init__(self, parent_plot_widget):
        super().__init__(parent_plot_widget)
        self.logger = logging.getLogger('PlotSettingsPanel')

        self.parent_plot = parent_plot_widget
        self.is_visible = False

        # Текущие настройки
        self.current_settings = PlotSettings()

        self.setup_ui()
        self.setup_animation()
        self.hide()  # Скрываем по умолчанию

        # Устанавливаем event filter для обработки кликов вне панели
        QApplication.instance().installEventFilter(self)

    def setup_ui(self):
        """Настройка интерфейса"""
        # Устанавливаем стиль панели
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f8f8;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QLabel {
                font-size: 11px;
            }
            QDoubleSpinBox, QCheckBox, QComboBox {
                font-size: 11px;
            }
        """)

        # Устанавливаем фиксированный размер (увеличен для новой настройки)
        self.setFixedSize(200, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Настройка временного окна
        time_layout = QHBoxLayout()
        time_label = QLabel("Окно времени (мин):")
        time_label.setFixedWidth(120)
        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setMinimum(1.0)
        self.time_spinbox.setMaximum(1440.0)
        self.time_spinbox.setSingleStep(1.0)
        self.time_spinbox.setDecimals(0)
        self.time_spinbox.setValue(self.current_settings.time_window_minutes)
        self.time_spinbox.valueChanged.connect(self._on_settings_changed)
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_spinbox)
        layout.addLayout(time_layout)

        # Чекбокс использования системного времени
        self.time_checkbox = QCheckBox("Использовать системное время")
        self.time_checkbox.setChecked(self.current_settings.use_system_time)
        self.time_checkbox.stateChanged.connect(self._on_settings_changed)
        layout.addWidget(self.time_checkbox)

        # Настройка режима заполнения
        fill_layout = QHBoxLayout()
        fill_label = QLabel("Режим заполнения:")
        fill_label.setFixedWidth(120)
        self.fill_combobox = QComboBox()
        self.fill_combobox.addItem("Скользящий справа", FillMode.ROLLING_RIGHT)
        self.fill_combobox.addItem("Сканирующее слева", FillMode.SWEEPING_LEFT)
        # Устанавливаем текущий режим
        current_index = 0 if self.current_settings.fill_mode == FillMode.ROLLING_RIGHT else 1
        self.fill_combobox.setCurrentIndex(current_index)
        self.fill_combobox.currentIndexChanged.connect(self._on_settings_changed)
        fill_layout.addWidget(fill_label)
        fill_layout.addWidget(self.fill_combobox)
        layout.addLayout(fill_layout)

    def setup_animation(self):
        """Настройка анимации появления/исчезновения"""
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(200)  # 200 мс

    def toggle_panel(self):
        """Переключить видимость панели"""
        if self.is_visible:
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self):
        """Показать панель с анимацией"""
        if self.is_visible:
            return

        self.is_visible = True
        self.show()

        # Позиционируем панель рядом с кнопкой настроек
        self.update_panel_position()

        start_rect = QRect(self.target_position.x(), self.target_position.y(), 0, self.height())
        end_rect = QRect(self.target_position.x() - self.width(), self.target_position.y(), self.width(), self.height())

        self.animation.setStartValue(start_rect)
        self.animation.setEndValue(end_rect)
        self.animation.start()

        self.logger.debug("Панель настроек показана")

    def update_panel_position(self):
        """Обновить позицию панели"""
        if not self.parent_plot:
            return

        # Привязываем панель к правому верхнему углу графика
        plot_rect = self.parent_plot.rect()
        plot_global_pos = self.parent_plot.mapToGlobal(QPoint(0, 0))
        panel_pos = self.parent().mapFromGlobal(plot_global_pos)

        # Позиционируем панель в правом верхнем углу графика
        self.target_position = QPoint(panel_pos.x() + plot_rect.width() - self.width(),
                                    panel_pos.y())

        # Если панель уже видна, обновляем ее позицию без анимации
        if self.is_visible:
            self.move(self.target_position.x(), self.target_position.y())

    def hide_panel(self):
        """Скрыть панель с анимацией"""
        if not self.is_visible:
            return

        self.is_visible = False

        current_rect = self.geometry()
        end_rect = QRect(current_rect.x() + current_rect.width(), current_rect.y(), 0, current_rect.height())

        self.animation.setStartValue(current_rect)
        self.animation.setEndValue(end_rect)
        self.animation.finished.connect(self._on_hide_finished)
        self.animation.start()

        self.logger.debug("Панель настроек скрыта")

    def _on_hide_finished(self):
        """Обработчик завершения анимации скрытия"""
        self.hide()
        self.animation.finished.disconnect(self._on_hide_finished)

    def _on_settings_changed(self):
        """Обработчик изменения настроек"""
        # Обновляем текущие настройки
        self.current_settings.time_window_minutes = int(self.time_spinbox.value())
        self.current_settings.use_system_time = self.time_checkbox.isChecked()
        self.current_settings.fill_mode = self.fill_combobox.currentData()

        # Отправляем сигнал
        self.settings_changed.emit()

        self.logger.debug(f"Настройки графика изменены: fill_mode={self.current_settings.fill_mode}")

    def apply_settings(self, settings: PlotSettings):
        """
        Применить настройки к панели

        Args:
            settings: Настройки для применения
        """
        self.current_settings = settings

        # Обновляем UI
        self.time_spinbox.blockSignals(True)
        self.time_spinbox.setValue(settings.time_window_minutes)
        self.time_spinbox.blockSignals(False)

        self.time_checkbox.blockSignals(True)
        self.time_checkbox.setChecked(settings.use_system_time)
        self.time_checkbox.blockSignals(False)

        # Обновляем QComboBox для режима заполнения
        self.fill_combobox.blockSignals(True)
        current_index = 0 if settings.fill_mode == FillMode.ROLLING_RIGHT else 1
        self.fill_combobox.setCurrentIndex(current_index)
        self.fill_combobox.blockSignals(False)

        self.logger.debug(f"Настройки применены к панели: fill_mode={settings.fill_mode}")

    def eventFilter(self, obj, event):
        """
        Обработчик событий для закрытия панели при клике вне ее области

        Args:
            obj: Объект, на котором произошло событие
            event: Событие

        Returns:
            True если событие обработано
        """
        if event.type() == QEvent.MouseButtonPress and self.is_visible:
            # Получаем позицию клика в координатах панели
            click_pos = self.mapFromGlobal(event.globalPos())

            # Если клик внутри геометрии панели - не закрываем
            if self.rect().contains(click_pos):
                return False

            # Если клик на кнопке настроек - не закрываем
            if obj == self.parent_plot.settings_button:
                return False

            # Клик вне панели - закрываем
            self.hide_panel()
            return True

        return super().eventFilter(obj, event)

    def _is_click_inside_panel(self, obj):
        """
        Проверить, находится ли объект клика внутри панели настроек

        Args:
            obj: Объект, на котором произошел клик

        Returns:
            True если клик внутри панели
        """
        # Проверяем кнопку настроек
        if obj == self.parent_plot.settings_button:
            return True

        # Проверяем саму панель и ее дочерние элементы
        current = obj
        while current is not None:
            if current == self:
                return True
            current = current.parent()

        return False
