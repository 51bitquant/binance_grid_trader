import ctypes
import platform
import sys
import traceback
import types

import qdarkstyle
from PyQt5 import QtGui, QtWidgets, QtCore

from .mainwindow import MainWindow
from ..setting import SETTINGS
from ..utility import get_icon_path

qapp = None


def excepthook(exctype: type, value: Exception, tb: types.TracebackType) -> None:
    """
    Raise exception under debug mode, otherwise
    show exception detail with QMessageBox.
    """
    sys.__excepthook__(exctype, value, tb)

    msg = "".join(traceback.format_exception(exctype, value, tb))
    # qapp.signal_exception.emit(msg)

    sys.stderr.write(msg)


def create_qapp(app_name: str = "Binance Grid Trader") -> QtWidgets.QApplication:
    """
    Create Qt Application.
    """
    global qapp

    sys.excepthook = excepthook

    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

    qapp = QtWidgets.QApplication(sys.argv)
    qapp.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    font = QtGui.QFont(SETTINGS["font.family"], SETTINGS["font.size"])
    qapp.setFont(font)

    icon = QtGui.QIcon(get_icon_path(__file__, "vnpy.ico"))
    qapp.setWindowIcon(icon)

    if "Windows" in platform.uname():
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            app_name
        )

    return qapp

