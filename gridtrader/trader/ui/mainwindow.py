"""
Implements main window of Grid Trader.
"""

from functools import partial
from typing import Callable, Dict, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets

import gridtrader
from gridtrader.event import EventEngine
from .widget import (
    ActiveOrderMonitor,
    LogMonitor,
    ConnectDialog
)

from ..engine import MainEngine
from ..utility import get_icon_path, TRADER_DIR
from .widget import  CtaManager


class MainWindow(QtWidgets.QMainWindow):
    """
    Main window of Grid Trader.
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(MainWindow, self).__init__()
        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.window_title: str = f"Binance Grid Trader {gridtrader.__version__} [{TRADER_DIR}]"

        self.widgets: Dict[str, QtWidgets.QWidget] = {}
        self.init_ui()
        self.init_menu()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle(self.window_title)

        """"""
        cta_widget, dock = self.create_dock(CtaManager, 'Strategies', QtCore.Qt.LeftDockWidgetArea)

        self.create_dock(
            ActiveOrderMonitor, "Active Orders", QtCore.Qt.RightDockWidgetArea
        )

        log_monitor, dock2 = self.create_dock(
            LogMonitor, "Logs", QtCore.Qt.RightDockWidgetArea
        )

        cta_widget.log_monitor = log_monitor

    def init_menu(self) -> None:
        """"""
        bar = self.menuBar()

        # System menu
        sys_menu = bar.addMenu("Config Binance API")

        gateway_names = self.main_engine.get_all_gateway_names()
        for name in gateway_names:
            func = partial(self.connect, name)
            self.add_menu_action(sys_menu, f"Connect {name}", "connect.ico", func)

    def add_menu_action(
            self,
            menu: QtWidgets.QMenu,
            action_name: str,
            icon_name: str,
            func: Callable,
    ) -> None:
        """"""
        icon = QtGui.QIcon(get_icon_path(__file__, icon_name))

        action = QtWidgets.QAction(action_name, self)
        action.triggered.connect(func)
        action.setIcon(icon)

        menu.addAction(action)

    def create_dock(
            self,
            widget_class: QtWidgets.QWidget,
            name: str,
            area: int
    ) -> Tuple[QtWidgets.QWidget, QtWidgets.QDockWidget]:
        """
        Initialize a dock widget.
        """
        widget = widget_class(self.main_engine, self.event_engine)

        dock = QtWidgets.QDockWidget(name)
        dock.setWidget(widget)
        dock.setObjectName(name)
        dock.setFeatures(dock.NoDockWidgetFeatures)
        self.addDockWidget(area, dock)
        return widget, dock

    def connect(self, gateway_name: str) -> None:
        """
        Open connect dialog for gateway connection.
        """
        dialog = ConnectDialog(self.main_engine, gateway_name)
        dialog.exec_()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Call main engine close function before exit.
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            "Exit",
            "Confirm Exit?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply == QtWidgets.QMessageBox.Yes:
            for widget in self.widgets.values():
                widget.close()

            self.main_engine.close()

            event.accept()
        else:
            event.ignore()

    def open_widget(self, widget_class: QtWidgets.QWidget, name: str) -> None:
        """
        Open contract manager.
        """
        widget = self.widgets.get(name, None)
        if not widget:
            widget = widget_class(self.main_engine, self.event_engine)
            self.widgets[name] = widget

        if isinstance(widget, QtWidgets.QDialog):
            widget.exec_()
        else:
            widget.show()
