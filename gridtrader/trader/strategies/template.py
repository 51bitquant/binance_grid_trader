""""""
from abc import ABC
from copy import copy
from typing import Any

from gridtrader.trader.constant import Direction, Offset
from gridtrader.trader.object import TickData, OrderData, TradeData
from gridtrader.trader.utility import virtual


class CtaTemplate(ABC):
    """"""

    author = ""
    parameters = []
    variables = []

    def __init__(
            self,
            cta_engine: Any,
            strategy_name: str,
            vt_symbol: str,
            setting: dict,
    ):
        """"""
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol

        self.inited = False
        self.trading = False
        self.pos = 0

        # Copy a new variables list here to avoid duplicate insert when multiple
        # strategy instances are created with the same strategy class.
        self.variables = copy(self.variables)
        self.variables.insert(0, "inited")
        self.variables.insert(1, "trading")
        self.variables.insert(2, "pos")

        self.update_setting(setting)

    def update_setting(self, setting: dict):
        """
        Update strategy parameter wtih value in setting dict.
        """
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    @classmethod
    def get_class_parameters(cls):
        """
        Get default parameters dict of strategy class.
        """
        class_parameters = {}
        for name in cls.parameters:
            class_parameters[name] = getattr(cls, name)
        return class_parameters

    def get_parameters(self):
        """
        Get strategy parameters dict.
        """
        strategy_parameters = {}
        for name in self.parameters:
            strategy_parameters[name] = getattr(self, name)
        return strategy_parameters

    def get_variables(self):
        """
        Get strategy variables dict.
        """
        strategy_variables = {}
        for name in self.variables:
            strategy_variables[name] = getattr(self, name)
        return strategy_variables

    def get_data(self):
        """
        Get strategy data.
        """
        strategy_data = {
            "strategy_name": self.strategy_name,
            "vt_symbol": self.vt_symbol,
            "class_name": self.__class__.__name__,
            "author": self.author,
            "parameters": self.get_parameters(),
            "variables": self.get_variables(),
        }
        return strategy_data

    @virtual
    def on_init(self):
        """
        Callback when strategy is inited.
        """
        pass

    @virtual
    def on_start(self):
        """
        Callback when strategy is started.
        """
        pass

    @virtual
    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        pass

    @virtual
    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        pass

    @virtual
    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        pass

    @virtual
    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass


    def buy(self, price: float, volume: float):
        """
        Send buy order to open a long position.
        """
        return self.send_order(Direction.LONG, Offset.OPEN, price, volume)

    def sell(self, price: float, volume: float):
        """
        Send sell order to close a long position.
        """
        return self.send_order(Direction.SHORT, Offset.CLOSE, price, volume)

    def short(self, price: float, volume: float):
        """
        Send short order to open as short position.
        """
        return self.send_order(Direction.SHORT, Offset.OPEN, price, volume)

    def cover(self, price: float, volume: float):
        """
        Send cover order to close a short position.
        """
        return self.send_order(Direction.LONG, Offset.CLOSE, price, volume)

    def send_order(self, direction: Direction, offset: Offset, price: float, volume: float):
        """
        Send a new order with logging.
        """
        if self.trading:
            vt_orderids = self.cta_engine.send_order(self, direction, offset, price, volume)
            print(
                f"Order Sent | Direction: {direction}, Offset: {offset}, Price: {price}, Volume: {volume}, Order IDs: {vt_orderids}")
            return vt_orderids
        else:
            return []

    def cancel_order(self, vt_orderid: str):
        """
        Cancel an existing order.
        """
        if self.trading:
            self.cta_engine.cancel_order(self, vt_orderid)

    def cancel_all(self):
        """
        Cancel all orders sent by strategy.
        """
        if self.trading:
            self.cta_engine.cancel_all(self)

    def write_log(self, msg: str):
        """
        Write a log message.
        """
        self.cta_engine.write_log(msg, self)

    def get_price_tick(self):
        """
        Return price tick data of trading contract.
        """
        return self.cta_engine.get_price_tick(self)

    def put_event(self):
        """
        Put an strategy data event for ui update.
        """
        if self.inited:
            self.cta_engine.put_strategy_event(self)

    def sync_data(self):
        """
        Sync strategy variables value into disk storage.
        """
        if self.trading:
            self.cta_engine.sync_strategy_data(self)
