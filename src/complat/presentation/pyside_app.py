from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from complat.presentation.assets import app_icon_path
from complat.presentation.pyside.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    _configure_application(app)
    icon = _load_app_icon()
    if icon:
        app.setWindowIcon(icon)

    window = MainWindow(app_icon=icon)
    tray = _create_system_tray(app, window, icon)
    if tray:
        app._complat_tray = tray

    window.show()
    raise SystemExit(app.exec())


def _configure_application(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0f172a"))
    palette.setColor(QPalette.WindowText, QColor("#e5e7eb"))
    palette.setColor(QPalette.Base, QColor("#0b1220"))
    palette.setColor(QPalette.AlternateBase, QColor("#101a2e"))
    palette.setColor(QPalette.Text, QColor("#f8fafc"))
    palette.setColor(QPalette.Button, QColor("#2563eb"))
    palette.setColor(QPalette.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def _load_app_icon() -> QIcon | None:
    path = app_icon_path()
    if not path:
        return None

    icon = QIcon(str(path))
    return None if icon.isNull() else icon


def _create_system_tray(
    app: QApplication,
    window: MainWindow,
    icon: QIcon | None,
) -> QSystemTrayIcon | None:
    if icon is None or not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("COMPLAT")

    menu = QMenu()
    show_action = QAction("Open COMPLAT", menu)
    quit_action = QAction("Quit", menu)

    show_action.triggered.connect(lambda: _show_window(window))
    quit_action.triggered.connect(app.quit)

    menu.addAction(show_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: _on_tray_activated(reason, window))
    tray.show()

    return tray


def _show_window(window: MainWindow) -> None:
    window.show()
    window.raise_()
    window.activateWindow()


def _on_tray_activated(reason, window: MainWindow) -> None:
    if reason == QSystemTrayIcon.DoubleClick:
        _show_window(window)


if __name__ == "__main__":
    main()
