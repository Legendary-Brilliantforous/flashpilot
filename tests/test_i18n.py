import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_language_switch_retranslates_existing_widgets():
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QLabel,
        QListWidget,
        QMenu,
        QTabWidget,
        QTableWidget,
        QTableWidgetItem,
        QWidget,
    )

    from python.gui.i18n import install_qt_hooks, set_language, translate

    app = QApplication.instance() or QApplication([])
    install_qt_hooks()

    label = QLabel("Application language")
    choices = QComboBox()
    choices.addItem("English", "en")
    choices.addItem("Türkçe", "tr")
    menu = QMenu()
    action = menu.addAction("English")
    options = QListWidget()
    options.addItem("English")
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "English")
    table = QTableWidget(1, 1)
    table_item = QTableWidgetItem("English")
    table.setItem(0, 0, table_item)

    set_language("tr")
    app.processEvents()
    assert translate("Application language") == "Arayüz dili"
    assert label.text() == "Arayüz dili"
    assert choices.itemText(0) == "İngilizce"
    assert action.text() == "İngilizce"
    assert options.item(0).text() == "İngilizce"
    assert tabs.tabText(0) == "İngilizce"
    assert table.item(0, 0).text() == "İngilizce"

    set_language("en")
    app.processEvents()
    assert label.text() == "Application language"
    assert choices.itemText(0) == "English"
    assert action.text() == "English"
    assert options.item(0).text() == "English"
    assert tabs.tabText(0) == "English"
    assert table.item(0, 0).text() == "English"
