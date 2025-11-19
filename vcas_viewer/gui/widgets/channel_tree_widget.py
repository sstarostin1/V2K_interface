# -*- coding: utf-8 -*-
"""
Виджет дерева каналов VCAS
"""

from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QApplication
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

import logging


class ChannelTreeWidget(QTreeWidget):
    """Виджет дерева каналов VCAS"""

    channel_selected = pyqtSignal(str)  # Сигнал при выборе канала
    directory_selected = pyqtSignal(str)  # Сигнал при выборе директории
    multiple_selected = pyqtSignal(list)  # Сигнал множественного выбора
    channels_dragged = pyqtSignal(list)  # Сигнал перетаскивания каналов
    selection_count_changed = pyqtSignal(int)  # Сигнал изменения количества выбранных элементов

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabel("Каналы VCAS")
        self.setMinimumWidth(300)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Настройка логирования
        self.logger = logging.getLogger('ChannelTreeWidget')

        # Настройка внешнего вида
        self.setFont(QFont("Consolas", 9))
        self.setAlternatingRowColors(True)

        # Множественный выбор
        self.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.selected_items = []
        self.anchor_item = None  # Anchor для множественного выбора
        self.selection_count = 0  # Счетчик выбранных элементов

    def _on_item_clicked(self, item, column):
        """Обработчик клика по элементу дерева"""
        modifiers = QApplication.keyboardModifiers()

        # Определяем, является ли элемент каналом или директорией
        channel_name = item.data(0, Qt.UserRole)
        item_text = item.text(0)

        if channel_name:
            # Это канал
            if modifiers == Qt.ShiftModifier:
                self._range_select(item)
                selected_channels = [i.data(0, Qt.UserRole) for i in self.selected_items if i.data(0, Qt.UserRole)]
                self.multiple_selected.emit(selected_channels)
            elif modifiers == Qt.ControlModifier:
                self._multi_select(item)
                selected_channels = [i.data(0, Qt.UserRole) for i in self.selected_items if i.data(0, Qt.UserRole)]
                self.multiple_selected.emit(selected_channels)
            else:
                # Одиночный выбор - сбрасываем множественный выбор
                self.clearSelection()
                self.selected_items = []
                self._single_select(item)
                self.channel_selected.emit(channel_name)
        else:
            # Это директория - только раскрываем/сворачиваем на клик и сбрасываем множественный выбор
            if item.childCount() > 0:
                # Используем QTimer для отложенного обновления интерфейса
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: item.setExpanded(not item.isExpanded()))
            # Сбрасываем множественный выбор при клике на директорию
            self.clearSelection()
            self.selected_items = []

    def update_channels(self, channels_list):
        """Обновить дерево каналов с правильной вложенной структурой"""
        self.logger.info(f"Обновление дерева каналов, получено {len(channels_list)} каналов")

        # Сохраняем текущие expanded состояния перед очисткой
        expanded_dirs = self._save_expanded_dirs()
        self.logger.debug(f"Сохранены expanded директории: {expanded_dirs}")

        # Полностью очищаем дерево перед обновлением
        self.clear()
        self.logger.debug("Дерево каналов очищено")

        if not channels_list:
            self.logger.warning("Получен пустой список каналов")
            return

        try:
            # Строим древовидную структуру каналов
            self.logger.debug("Построение структуры каналов...")
            root_structure = self._build_channel_structure(channels_list)
            self.logger.info(f"Построена структура: {len(root_structure)} корневых элементов")

            # Создаем дерево из структуры
            self.logger.debug("Создание дерева из структуры...")
            self._create_tree_from_structure(root_structure, None)
            self.logger.info("Дерево каналов создано")

            # Откладываем восстановление expanded состояний до следующего цикла обработки событий
            # Это предотвращает конфликты с немедленным обновлением интерфейса
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._restore_expanded_dirs_improved(expanded_dirs))
            self.logger.debug("Запланировано восстановление expanded директорий")

        except Exception as e:
            self.logger.error(f"Ошибка при построении дерева каналов: {str(e)}")
            self.logger.info("Переход к плоской структуре из-за ошибки")

            # Fallback: создаем простую плоскую структуру
            self._create_flat_structure(channels_list)

        # Сохраняем expanded_dirs в Config
        # Также откладываем сохранение конфигурации
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._save_expanded_config())
        self.logger.debug("Запланировано сохранение конфигурации")

    def _create_flat_structure(self, channels_list):
        """Создать простую плоскую структуру каналов (fallback)"""
        self.logger.info("Создание плоской структуры каналов")

        for channel in channels_list:
            # Создаем элемент для каждого канала
            item = QTreeWidgetItem([channel])
            item.setFont(0, QFont("Consolas", 8))
            item.setData(0, Qt.UserRole, channel)  # Сохраняем полное имя канала

            # Добавляем элемент в корень дерева
            self.addTopLevelItem(item)
            self.logger.debug(f"Добавлен канал в плоской структуре: {channel}")

        self.logger.info(f"Создана плоская структура с {len(channels_list)} каналами")

    def _build_channel_structure(self, channels_list):
        """Построить древовидную структуру каналов"""
        root = {}
        self.logger.info(f"Построение структуры для {len(channels_list)} каналов")

        # Показываем примеры каналов для диагностики
        if channels_list:
            self.logger.info(f"Примеры каналов: {channels_list[:5]}")

        # Диагностика форматов каналов
        slash_count = sum(1 for ch in channels_list if '/' in ch)
        dot_count = sum(1 for ch in channels_list if '.' in ch and '/' not in ch)
        no_sep_count = sum(1 for ch in channels_list if '/' not in ch and '.' not in ch)

        self.logger.info(f"Формат каналов: {slash_count} со слешами, {dot_count} с точками, {no_sep_count} без разделителей")

        for i, channel in enumerate(channels_list):
            if not channel or not isinstance(channel, str):
                self.logger.warning(f"Пропускаем некорректный канал {i+1}: {channel}")
                continue

            # Пробуем парсить по слешу, если нет слешей - по точке
            if '/' in channel:
                parts = channel.split('/')
                separator = '/'
            else:
                parts = channel.split('.')
                separator = '.'

            current_level = root

            self.logger.debug(f"Парсинг канала {i+1}: '{channel}' -> {parts} (разделитель: {separator})")

            # Проходим по всем частям пути, кроме последней
            for part in parts[:-1]:
                if not part:  # Пропускаем пустые части
                    continue
                if part not in current_level:
                    current_level[part] = {}
                    self.logger.debug(f"  Создана директория: {part}")
                current_level = current_level[part]

            # Добавляем конечный канал
            final_part = parts[-1] if parts else channel
            if final_part:
                current_level[final_part] = channel  # Сохраняем полное имя канала
                self.logger.debug(f"  Добавлен канал: {final_part}")

        self.logger.info(f"Корневые элементы: {list(root.keys())}")
        self.logger.info(f"Структура построена: {len(root)} корневых директорий")

        # Детальная диагностика структуры
        for root_dir, content in root.items():
            if isinstance(content, dict):
                channel_count = sum(1 for v in content.values() if not isinstance(v, dict))
                self.logger.info(f"Директория '{root_dir}': {channel_count} каналов, {len([v for v in content.values() if isinstance(v, dict)])} поддиректорий")
            else:
                self.logger.info(f"Корневой канал '{root_dir}': {content}")

        return root

    def _create_tree_from_structure(self, structure, parent_item):
        """Рекурсивно создать дерево из структуры"""
        if not structure:
            self.logger.debug("Пустая структура, пропускаем создание дерева")
            return

        self.logger.debug(f"Создание дерева из структуры с {len(structure)} элементами")

        for name, value in sorted(structure.items()):
            self.logger.debug(f"Обработка элемента: {name}, тип: {'директория' if isinstance(value, dict) else 'канал'}")

            # Создаем элемент дерева
            item = QTreeWidgetItem([name])

            # Настраиваем внешний вид
            if isinstance(value, dict):
                # Это директория
                item.setFont(0, QFont("Consolas", 9, QFont.Bold))
                item.setForeground(0, self.palette().color(self.palette().ColorRole.Text))
                self.logger.debug(f"Создана директория: {name}")
            else:
                # Это канал (конечный элемент)
                item.setFont(0, QFont("Consolas", 8))
                item.setData(0, Qt.UserRole, value)  # Сохраняем полное имя канала
                self.logger.debug(f"Добавлен канал: {name} -> {value}")

            # Добавляем элемент в дерево
            if parent_item is None:
                self.addTopLevelItem(item)
                self.logger.debug(f"Добавлен корневой элемент: {name}")
            else:
                parent_item.addChild(item)
                self.logger.debug(f"Добавлен дочерний элемент: {name} к {parent_item.text(0)}")

            # Если это директория, рекурсивно обрабатываем вложенные элементы
            if isinstance(value, dict):
                self.logger.debug(f"Рекурсивная обработка директории: {name}")
                self._create_tree_from_structure(value, item)
                # Не устанавливаем setExpanded(False), полагаемся на восстановление
                self.logger.debug(f"Директория {name} создана")

    def _get_expanded_dirs(self):
        """Получить список раскрытых директорий"""
        expanded = []
        def collect_expanded(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.isExpanded() and child.childCount() > 0:
                    expanded.append(child.text(0))
                    collect_expanded(child)
        collect_expanded(self.invisibleRootItem())
        return expanded

    def _save_expanded_dirs(self):
        """Сохранить текущие раскрытые директории в виде путей"""
        expanded_paths = []
        def collect_paths(parent, path=""):
            for i in range(parent.childCount()):
                child = parent.child(i)
                current_path = f"{path}/{child.text(0)}" if path else child.text(0)
                if child.isExpanded() and child.childCount() > 0:
                    expanded_paths.append(current_path)
                    collect_paths(child, current_path)
        collect_paths(self.invisibleRootItem())
        return expanded_paths

    def _restore_expanded_dirs_improved(self, expanded_paths):
        """Восстановить раскрытые директории по путям"""
        if not expanded_paths:
            return

        def expand_by_path(parent, path_parts, index=0):
            if index >= len(path_parts):
                return
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.text(0) == path_parts[index] and child.childCount() > 0:
                    child.setExpanded(True)
                    expand_by_path(child, path_parts, index + 1)

        for path in expanded_paths:
            parts = path.split('/')
            expand_by_path(self.invisibleRootItem(), parts)

    def _save_expanded_config(self):
        """Сохранить текущие раскрытые директории в конфигурацию"""
        from ...core.config import Config
        Config.EXPANDED_DIRS = self._get_expanded_dirs()
        Config.save_config()

    def _single_select(self, item):
        """Одиночный выбор"""
        self.clearSelection()
        item.setSelected(True)
        self.setCurrentItem(item)
        self.selected_items = [item]
        self.anchor_item = item  # Устанавливаем anchor
        self.selection_count = 1
        self.selection_count_changed.emit(self.selection_count)

    def _multi_select(self, item):
        """Множественный выбор с Ctrl"""
        if item in self.selected_items:
            self.selected_items.remove(item)
            item.setSelected(False)
        else:
            self.selected_items.append(item)
            item.setSelected(True)
        self.selection_count = len(self.selected_items)
        self.selection_count_changed.emit(self.selection_count)

    def _range_select(self, item):
        """Выбор диапазона с Shift"""
        if not self.anchor_item:
            self._single_select(item)
            return

        # Найти индексы anchor и текущего
        all_items = self._get_all_items()
        current_index = all_items.index(item)
        anchor_index = all_items.index(self.anchor_item)

        start = min(current_index, anchor_index)
        end = max(current_index, anchor_index)

        self.clearSelection()
        for i in range(start, end + 1):
            all_items[i].setSelected(True)
        self.selected_items = all_items[start:end+1]
        self.selection_count = len(self.selected_items)
        self.selection_count_changed.emit(self.selection_count)

    def _get_all_items(self):
        """Получить список всех элементов дерева"""
        items = []
        def collect_items(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                items.append(child)
                if child.childCount() > 0:
                    collect_items(child)
        collect_items(self.invisibleRootItem())
        return items

    def _on_item_double_clicked(self, item, column):
        """Обработчик двойного клика по элементу дерева"""
        # Определяем, является ли элемент каналом или директорией
        channel_name = item.data(0, Qt.UserRole)
        item_text = item.text(0)

        if not channel_name:
            # Это директория - выбираем и отправляем сигнал
            self._single_select(item)
            self.directory_selected.emit(item_text)

    def startDrag(self, supportedActions):
        """Начало перетаскивания"""
        selected_channels = [item.data(0, Qt.UserRole) for item in self.selected_items if item.data(0, Qt.UserRole)]
        if selected_channels:
            self.channels_dragged.emit(selected_channels)
        super().startDrag(supportedActions)
