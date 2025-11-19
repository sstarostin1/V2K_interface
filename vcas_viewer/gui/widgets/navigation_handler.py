# -*- coding: utf-8 -*-
"""
Обработчик навигации для дерева каналов
"""

from PyQt5.QtCore import Qt


class NavigationHandler:
    """Обработчик навигации и клавиш для дерева каналов"""

    def __init__(self, tree_widget):
        self.tree_widget = tree_widget

    def handle_key(self, event):
        """Обработать нажатие клавиши"""
        key = event.key()

        if key == Qt.Key_Up:
            self._move_up()
            return True
        elif key == Qt.Key_Down:
            self._move_down()
            return True
        elif key == Qt.Key_Left:
            self._collapse_item()
            return True
        elif key == Qt.Key_Right:
            self._expand_item()
            return True
        elif key == Qt.Key_Space:
            self._toggle_expand()
            return True
        elif key == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            self._select_all()
            return True

        return False

    def _move_up(self):
        """Переместиться вверх"""
        current = self.tree_widget.currentItem()
        if not current:
            return

        # Найти предыдущий элемент
        prev_item = self._get_previous_item(current)
        if prev_item:
            self.update_selection(prev_item, event.modifiers() if 'event' in locals() else Qt.NoModifier)

    def _move_down(self):
        """Переместиться вниз"""
        current = self.tree_widget.currentItem()
        if not current:
            return

        # Найти следующий элемент
        next_item = self._get_next_item(current)
        if next_item:
            self.update_selection(next_item, event.modifiers() if 'event' in locals() else Qt.NoModifier)

    def _get_previous_item(self, item):
        """Получить предыдущий элемент в дереве"""
        # Сначала пробуем найти предыдущего sibling
        parent = item.parent() or self.tree_widget.invisibleRootItem()
        index = parent.indexOfChild(item)

        if index > 0:
            # Есть предыдущий sibling
            prev_sibling = parent.child(index - 1)
            # Если sibling раскрыт и имеет детей, возвращаем последнего потомка
            if prev_sibling.isExpanded() and prev_sibling.childCount() > 0:
                return self._get_last_descendant(prev_sibling)
            else:
                return prev_sibling
        else:
            # Это первый ребенок, возвращаем родителя
            if parent != self.tree_widget.invisibleRootItem():
                return parent

        return None

    def _get_next_item(self, item):
        """Получить следующий элемент в дереве"""
        # Если элемент раскрыт и имеет детей, возвращаем первого ребенка
        if item.isExpanded() and item.childCount() > 0:
            return item.child(0)

        # Ищем следующего sibling
        parent = item.parent() or self.tree_widget.invisibleRootItem()
        index = parent.indexOfChild(item)

        if index < parent.childCount() - 1:
            # Есть следующий sibling
            return parent.child(index + 1)

        # Ищем следующего у родителя
        current_parent = parent
        while current_parent != self.tree_widget.invisibleRootItem():
            grandparent = current_parent.parent() or self.tree_widget.invisibleRootItem()
            parent_index = grandparent.indexOfChild(current_parent)

            if parent_index < grandparent.childCount() - 1:
                return grandparent.child(parent_index + 1)

            current_parent = grandparent

        return None

    def _get_last_descendant(self, item):
        """Получить последнего потомка элемента"""
        if not item.isExpanded() or item.childCount() == 0:
            return item

        return self._get_last_descendant(item.child(item.childCount() - 1))

    def _collapse_item(self):
        """Свернуть текущий элемент"""
        current = self.tree_widget.currentItem()
        if current and current.isExpanded() and current.childCount() > 0:
            current.setExpanded(False)

    def _expand_item(self):
        """Раскрыть текущий элемент"""
        current = self.tree_widget.currentItem()
        if current and not current.isExpanded() and current.childCount() > 0:
            current.setExpanded(True)

    def _toggle_expand(self):
        """Переключить состояние раскрытия"""
        current = self.tree_widget.currentItem()
        if current and current.childCount() > 0:
            current.setExpanded(not current.isExpanded())

    def _select_all(self):
        """Выбрать все элементы"""
        self.tree_widget.selectAll()

    def update_selection(self, modifiers=Qt.NoModifier):
        """Обновить выбор с учетом модификаторов"""
        current = self.tree_widget.currentItem()
        if current:
            self.tree_widget.setCurrentItem(current)
            self._update_selection_after_move(modifiers)

    def _update_selection_after_move(self, modifiers):
        """Обновить выбор после перемещения"""
        current = self.tree_widget.currentItem()
        if not current:
            return

        if modifiers & Qt.ShiftModifier:
            # Расширенный выбор
            self.tree_widget._range_select(current)
        elif modifiers & Qt.ControlModifier:
            # Множественный выбор
            self.tree_widget._multi_select(current)
        else:
            # Одиночный выбор
            self.tree_widget._single_select(current)

    def get_selected_channels(self):
        """Получить список выбранных каналов"""
        return [item.data(0, Qt.UserRole) for item in self.tree_widget.selected_items if item.data(0, Qt.UserRole)]

    def set_active_item(self, item):
        """Установить активный элемент"""
        self.tree_widget.setCurrentItem(item)
