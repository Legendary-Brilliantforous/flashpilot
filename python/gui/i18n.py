"""Small runtime localization layer for the PyQt interface."""

import json
from pathlib import Path


_LANGUAGE = "tr"
_CATALOG = {}
_TEXT_PROPERTIES = []
_HOOKS_INSTALLED = False


def _load_catalog():
    catalog = {}
    catalog_dir = Path(__file__).with_name("translations")
    if not catalog_dir.exists():
        return catalog
    for path in sorted(catalog_dir.glob("*.json")):
        with path.open(encoding="utf-8") as source:
            data = json.load(source)
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in data.items()
        ):
            raise ValueError(f"Invalid translation catalog: {path}")
        catalog.update(data)
    return catalog


_CATALOG = _load_catalog()


def translate(text):
    """Translate a known English interface string; leave other text intact."""
    if not isinstance(text, str) or _LANGUAGE == "en":
        return text
    return _CATALOG.get(text, text)


def language():
    return _LANGUAGE


def _remember(obj, property_name, text):
    if isinstance(text, str):
        setattr(obj, property_name, text)


def _patch_text_argument(cls, method_name, argument_index, property_name,
                         keyword=None):
    original = getattr(cls, method_name, None)
    if original is None or getattr(original, "_flashpilot_i18n", False):
        return

    def localized(self, *args, **kwargs):
        args = list(args)
        text = None
        if len(args) > argument_index:
            text = args[argument_index]
            if isinstance(text, str):
                _remember(self, property_name, text)
                args[argument_index] = translate(text)
        elif keyword and isinstance(kwargs.get(keyword), str):
            text = kwargs[keyword]
            _remember(self, property_name, text)
            kwargs[keyword] = translate(text)
        return original(self, *args, **kwargs)

    localized._flashpilot_i18n = True
    setattr(cls, method_name, localized)
    _TEXT_PROPERTIES.append((property_name, method_name))


def _patch_constructor(cls, argument_index, property_name, keyword=None):
    original = cls.__init__
    if getattr(original, "_flashpilot_i18n", False):
        return

    def localized(self, *args, **kwargs):
        args = list(args)
        text = None
        if len(args) > argument_index:
            text = args[argument_index]
            if isinstance(text, str):
                args[argument_index] = translate(text)
        elif keyword and isinstance(kwargs.get(keyword), str):
            text = kwargs[keyword]
            kwargs[keyword] = translate(text)
        original(self, *args, **kwargs)
        if isinstance(text, str):
            _remember(self, property_name, text)

    localized._flashpilot_i18n = True
    cls.__init__ = localized


def _patch_combo_box(combo_box):
    original_add_item = combo_box.addItem
    original_add_items = combo_box.addItems
    original_set_item_text = combo_box.setItemText
    original_clear = combo_box.clear

    def sources(self):
        if not hasattr(self, "_flashpilot_i18n_items"):
            self._flashpilot_i18n_items = {}
        return self._flashpilot_i18n_items

    def add_item(self, *args, **kwargs):
        args = list(args)
        text_index = 1 if args and not isinstance(args[0], str) else 0
        if len(args) > text_index and isinstance(args[text_index], str):
            text = args[text_index]
            args[text_index] = translate(text)
            result = original_add_item(self, *args, **kwargs)
            sources(self)[self.count() - 1] = text
            return result
        return original_add_item(self, *args, **kwargs)

    def add_items(self, texts):
        texts = list(texts)
        start = self.count()
        result = original_add_items(self, [translate(text) for text in texts])
        for offset, text in enumerate(texts):
            if isinstance(text, str):
                sources(self)[start + offset] = text
        return result

    def set_item_text(self, index, text):
        if isinstance(text, str):
            sources(self)[index] = text
            text = translate(text)
        return original_set_item_text(self, index, text)

    def clear(self):
        result = original_clear(self)
        sources(self).clear()
        return result

    combo_box.addItem = add_item
    combo_box.addItems = add_items
    combo_box.setItemText = set_item_text
    combo_box.clear = clear


def _patch_menu_text(menu_type):
    original_add_action = menu_type.addAction
    original_add_menu = menu_type.addMenu

    def add_action(self, action, *args, **kwargs):
        if isinstance(action, str):
            source = action
            action = original_add_action(self, translate(source), *args, **kwargs)
            _remember(action, "_fp_text", source)
            return action
        return original_add_action(self, action, *args, **kwargs)

    def add_menu(self, menu, *args, **kwargs):
        if isinstance(menu, str):
            source = menu
            menu = original_add_menu(self, translate(source), *args, **kwargs)
            _remember(menu.menuAction(), "_fp_text", source)
            return menu
        return original_add_menu(self, menu, *args, **kwargs)

    menu_type.addAction = add_action
    menu_type.addMenu = add_menu


def _patch_list_widget(list_widget):
    original_add_item = list_widget.addItem

    def add_item(self, item):
        if isinstance(item, str):
            source = item
            original_add_item(self, translate(source))
            if not hasattr(self, "_flashpilot_i18n_items"):
                self._flashpilot_i18n_items = {}
            self._flashpilot_i18n_items[self.count() - 1] = source
            return
        original_add_item(self, item)

    list_widget.addItem = add_item


def _patch_indexed_text(cls, method_name, argument_index, prefix):
    original = getattr(cls, method_name)
    if getattr(original, "_flashpilot_i18n", False):
        return

    def localized(self, *args, **kwargs):
        args = list(args)
        if len(args) > argument_index and isinstance(args[argument_index], str):
            index = args[0]
            text = args[argument_index]
            setattr(self, f"{prefix}{index}", text)
            args[argument_index] = translate(text)
        return original(self, *args, **kwargs)

    localized._flashpilot_i18n = True
    setattr(cls, method_name, localized)


def _patch_tab_add(tab_widget, method_name, original, text_index_for_args):
    def localized(self, *args, **kwargs):
        args = list(args)
        text_index = text_index_for_args(args)
        if text_index is not None and len(args) > text_index:
            text = args[text_index]
            if isinstance(text, str):
                args[text_index] = translate(text)
                index = original(self, *args, **kwargs)
                setattr(self, f"_fp_tab_{index}", text)
                return index
        return original(self, *args, **kwargs)

    setattr(tab_widget, method_name, localized)


def _patch_tabs(tab_widget):
    original_add_tab = tab_widget.addTab
    original_insert_tab = tab_widget.insertTab

    def add_text_index(args):
        if len(args) > 1:
            return 2 if not isinstance(args[1], str) and len(args) > 2 else 1
        return None

    def insert_text_index(args):
        if len(args) > 2:
            return 3 if not isinstance(args[2], str) and len(args) > 3 else 2
        return None

    _patch_tab_add(tab_widget, "addTab", original_add_tab, add_text_index)
    _patch_tab_add(tab_widget, "insertTab", original_insert_tab, insert_text_index)


def install_qt_hooks():
    """Translate standard Qt text entry points without changing widget APIs."""
    global _HOOKS_INSTALLED
    if _HOOKS_INSTALLED:
        return

    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QAbstractButton,
        QCheckBox,
        QComboBox,
        QGroupBox,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMenu,
        QMessageBox,
        QPushButton,
        QRadioButton,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QWidget,
    )

    _patch_text_argument(QAbstractButton, "setText", 0, "_fp_text")
    _patch_text_argument(QLabel, "setText", 0, "_fp_text")
    _patch_text_argument(QGroupBox, "setTitle", 0, "_fp_title")
    _patch_text_argument(QWidget, "setWindowTitle", 0, "_fp_window_title")
    _patch_text_argument(QWidget, "setToolTip", 0, "_fp_tooltip")
    _patch_text_argument(QWidget, "setWhatsThis", 0, "_fp_whats_this")
    _patch_text_argument(QWidget, "setAccessibleName", 0, "_fp_accessible_name")
    _patch_text_argument(
        QWidget, "setAccessibleDescription", 0, "_fp_accessible_description")
    _patch_text_argument(QLineEdit, "setPlaceholderText", 0, "_fp_placeholder")
    _patch_text_argument(QTextEdit, "setPlaceholderText", 0, "_fp_placeholder")
    _patch_text_argument(QTextEdit, "setPlainText", 0, "_fp_plain_text")
    _patch_text_argument(QMessageBox, "setText", 0, "_fp_text")
    _patch_text_argument(
        QMessageBox, "setInformativeText", 0, "_fp_informative_text")
    _patch_text_argument(
        QMessageBox, "setDetailedText", 0, "_fp_detailed_text")
    _patch_text_argument(
        QListWidgetItem, "setText", 0, "_fp_item_text")
    _patch_text_argument(QAction, "setText", 0, "_fp_text")
    _patch_text_argument(QAction, "setToolTip", 0, "_fp_tooltip")
    _patch_indexed_text(QTabWidget, "setTabText", 1, "_fp_tab_")
    _patch_text_argument(QTableWidgetItem, "setText", 0, "_fp_item_text")
    for widget_type, property_name in (
        (QLabel, "_fp_text"),
        (QPushButton, "_fp_text"),
        (QCheckBox, "_fp_text"),
        (QRadioButton, "_fp_text"),
        (QGroupBox, "_fp_title"),
    ):
        _patch_constructor(
            widget_type, 0, property_name,
            "title" if widget_type is QGroupBox else "text")
    _patch_constructor(QListWidgetItem, 0, "_fp_item_text")
    _patch_constructor(QTableWidgetItem, 0, "_fp_item_text")
    _patch_combo_box(QComboBox)
    _patch_menu_text(QMenu)
    _patch_list_widget(QListWidget)
    _patch_tabs(QTabWidget)

    _HOOKS_INSTALLED = True


def set_language(value):
    """Set the UI language and retranslate existing widgets."""
    global _LANGUAGE
    _LANGUAGE = "en" if str(value).lower().startswith("en") else "tr"

    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QListWidget,
        QTabWidget,
        QTableWidget,
    )

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.allWidgets():
        for property_name, method_name in _TEXT_PROPERTIES:
            source = getattr(widget, property_name, None)
            if isinstance(source, str):
                getattr(widget, method_name)(source)
        if isinstance(widget, QComboBox):
            for index, source in getattr(
                widget, "_flashpilot_i18n_items", {}).items():
                if index < widget.count():
                    widget.setItemText(index, source)
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                source = getattr(widget, f"_fp_tab_{index}", None)
                if isinstance(source, str):
                    widget.setTabText(index, source)
        if isinstance(widget, QListWidget):
            for index, source in getattr(
                widget, "_flashpilot_i18n_items", {}).items():
                if index < widget.count():
                    widget.item(index).setText(source)
        for action in widget.actions():
            for property_name, method_name in _TEXT_PROPERTIES:
                source = getattr(action, property_name, None)
                if isinstance(source, str):
                    getattr(action, method_name)(source)
        if isinstance(widget, QTableWidget):
            for row in range(widget.rowCount()):
                for column in range(widget.columnCount()):
                    item = widget.item(row, column)
                    source = getattr(item, "_fp_item_text", None)
                    if item is not None and isinstance(source, str):
                        item.setText(source)
