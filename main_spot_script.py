from time import sleep
from logging import INFO

from gridtrader.event import EventEngine
from gridtrader.trader.engine import MainEngine, CtaEngine
from gridtrader.trader.setting import SETTINGS

SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True


def run_spot_strategy():
    SETTINGS["log.file"] = True

    event_engine = EventEngine()
    main_engine: MainEngine = MainEngine(event_engine)

    main_engine.write_log("create main engine")

    main_engine.connect(spot_settings, "Spot")
    main_engine.write_log("Connect Binance Spot Api")

    sleep(10)

    cta_engine: CtaEngine = main_engine.get_engine('strategy')
    cta_engine.init_engine()
    main_engine.write_log("Init Strategy Engine.")

    cta_engine.init_all_strategies()
    sleep(60)  # Leave enough time to complete strategy initialization
    main_engine.write_log("Init All Strategies.")

    cta_engine.start_all_strategies()
    main_engine.write_log("Start All Strategies.")

    while True:
        sleep(10)


if __name__ == "__main__":
    # the spot script, no ui, if you want to use the window UI, please use the main.py
    # before running, remember to past your api here.
    spot_settings = {
        "key": "past your api key from binance exchange",
        "secret": "past your api secret from binance exchange",
        "proxy_host": "",
        "proxy_port": 0
    }

    run_spot_strategy()
