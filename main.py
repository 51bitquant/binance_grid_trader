
from gridtrader.event import EventEngine

from gridtrader.trader.engine import MainEngine
from gridtrader.trader.ui import MainWindow, create_qapp


if __name__ == "__main__":
    """
    """
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    qapp = create_qapp()
    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    qapp.exec()
