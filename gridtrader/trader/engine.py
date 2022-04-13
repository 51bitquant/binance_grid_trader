"""
"""

import logging
import sys
import os
import traceback
from abc import ABC
from typing import Sequence, Dict, List, Optional
from decimal import Decimal

from gridtrader.event import Event, EventEngine
from gridtrader.event import (
    EVENT_TICK,
    EVENT_TIMER,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_CTA_LOG,
    EVENT_CTA_STRATEGY
)
from .gateway import BaseGateway
from .object import (
    CancelRequest,
    QueryRequest,
    LogData,
    OrderRequest,
    SubscribeRequest,
    OrderData,
    TickData,
    TradeData,
    PositionData,
    AccountData,
    ContractData
)
from .setting import SETTINGS
from .utility import get_folder_path, TRADER_DIR
from gridtrader.gateway.binance.binance_gateway import BinanceGateway
from gridtrader.gateway.binances.binances_gateway import BinancesGateway
from .strategies.template import CtaTemplate

from collections import defaultdict
from typing import Any, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from copy import copy

from gridtrader.trader.constant import (
    Direction,
    OrderType,
    Offset
)

from gridtrader.trader.utility import load_json, save_json, extract_vt_symbol, round_to, floor_to


class MainEngine:
    """
    Acts as the core of Grid Trader.
    """

    def __init__(self, event_engine: EventEngine = None):
        """"""
        if event_engine:
            self.event_engine: EventEngine = event_engine
        else:
            self.event_engine = EventEngine()
        self.event_engine.start()

        self.gateways: Dict[str, BaseGateway] = {}
        self.engines: Dict[str, BaseEngine] = {}

        os.chdir(TRADER_DIR)  # Change working directory

        self.spot_gateway = BinanceGateway(self.event_engine)
        self.future_gateway = BinancesGateway(self.event_engine)

        self.gateways[self.spot_gateway.gateway_name] = self.spot_gateway
        self.gateways[self.future_gateway.gateway_name] = self.future_gateway

        self.init_engines()  # Initialize function engines

    def init_engines(self) -> None:
        """
        Init all engines.
        """
        self.add_engine(CtaEngine)
        self.add_engine(LogEngine)
        self.add_engine(OmsEngine)

    def add_engine(self, engine_class: Any) -> None:
        """
        Add function engine.
        """
        engine = engine_class(self, self.event_engine)
        self.engines[engine.engine_name] = engine

    def write_log(self, msg: str, source: str = "") -> None:
        """
        Put log event with specific message.
        """
        log = LogData(msg=msg, gateway_name=source)
        event = Event(EVENT_LOG, log)
        self.event_engine.put(event)

    def get_gateway(self, gateway_name: str) -> BaseGateway:
        """
        Return gateway object by name.
        """
        gateway = self.gateways.get(gateway_name, None)
        if not gateway:
            self.write_log(f"Missing Exchange Gateway：{gateway_name}")
        return gateway

    def get_engine(self, engine_name: str) -> "BaseEngine":
        """
        Return engine object by name.
        """
        engine = self.engines.get(engine_name, None)
        if not engine:
            self.write_log(f"Missing Engine：{engine_name}")
        return engine

    def get_default_setting(self, gateway_name: str) -> Optional[Dict[str, Any]]:
        """
        Get default setting dict of a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            return gateway.get_default_setting()
        return None

    def get_all_gateway_names(self) -> List[str]:
        """
        Get all names of gateway added in main engine.
        """
        return list(self.gateways.keys())

    def connect(self, setting: dict, gateway_name: str) -> None:
        """
        Start connection of a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            gateway.connect(setting)

    def subscribe(self, req: SubscribeRequest, gateway_name: str) -> None:
        """
        Subscribe tick data update of a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            gateway.subscribe(req)

    def send_order(self, req: OrderRequest, gateway_name: str) -> str:
        """
        Send new order request to a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            return gateway.send_order(req)
        else:
            return ""

    def cancel_order(self, req: CancelRequest, gateway_name: str) -> None:
        """
        Send cancel order request to a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            gateway.cancel_order(req)

    def query_order(self, req: QueryRequest, gateway_name: str) -> None:
        """
        Send query order request to a specific gateway.
        """
        gateway = self.get_gateway(gateway_name)
        if gateway and hasattr(gateway, 'query_order'):
            gateway.query_order(req)

    def send_orders(self, reqs: Sequence[OrderRequest], gateway_name: str) -> List[str]:
        """
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            return gateway.send_orders(reqs)
        else:
            return ["" for req in reqs]

    def cancel_orders(self, reqs: Sequence[CancelRequest], gateway_name: str) -> None:
        """
        """
        gateway = self.get_gateway(gateway_name)
        if gateway:
            gateway.cancel_orders(reqs)

    def query_position(self):
        """
        query the position
        """
        for gateway in self.gateways.values():
            gateway.query_position()

    def query_account(self):
        """
        query the account
        """
        for gateway in self.gateways.values():
            gateway.query_account()

    def close(self) -> None:
        """
        Make sure every gateway and app is closed properly before
        programme exit.
        """
        # Stop event engine first to prevent new timer event.
        self.event_engine.stop()

        for engine in self.engines.values():
            engine.close()

        for gateway in self.gateways.values():
            gateway.close()


class BaseEngine(ABC):
    """
    Abstract class for implementing an function engine.
    """

    def __init__(
            self,
            main_engine: MainEngine,
            event_engine: EventEngine,
            engine_name: str,
    ):
        """"""
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.engine_name = engine_name

    def close(self):
        """"""
        pass


class LogEngine(BaseEngine):
    """
    Processes log event and output with logging module.
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(LogEngine, self).__init__(main_engine, event_engine, "log")

        if not SETTINGS["log.active"]:
            return

        self.level: int = SETTINGS["log.level"]

        self.logger: logging.Logger = logging.getLogger("Binance Grid Trader")
        self.logger.setLevel(self.level)

        self.formatter = logging.Formatter(
            "%(asctime)s  %(levelname)s: %(message)s"
        )

        self.add_null_handler()

        if SETTINGS["log.console"]:
            self.add_console_handler()

        if SETTINGS["log.file"]:
            self.add_file_handler()

        self.register_event()

    def add_null_handler(self) -> None:
        """
        Add null handler for logger.
        """
        null_handler = logging.NullHandler()
        self.logger.addHandler(null_handler)

    def add_console_handler(self) -> None:
        """
        Add console output of log.
        """
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.level)
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)

    def add_file_handler(self) -> None:
        """
        Add file output of log.
        """
        today_date = datetime.now().strftime("%Y%m%d")
        filename = f"vt_{today_date}.log"
        log_path = get_folder_path("log")
        file_path = log_path.joinpath(filename)

        file_handler = logging.FileHandler(
            file_path, mode="a", encoding="utf8"
        )
        file_handler.setLevel(self.level)
        file_handler.setFormatter(self.formatter)
        self.logger.addHandler(file_handler)

    def register_event(self) -> None:
        """"""
        self.event_engine.register(EVENT_LOG, self.process_log_event)

    def process_log_event(self, event: Event) -> None:
        """
        Process log event.
        """
        log = event.data
        self.logger.log(log.level, log.msg)


class OmsEngine(BaseEngine):
    """
    Provides order management system function for Grid Trader.
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(OmsEngine, self).__init__(main_engine, event_engine, "oms")

        self.ticks: Dict[str, TickData] = {}
        self.positions: Dict[str, PositionData] = {}
        self.accounts: Dict[str, AccountData] = {}
        self.contracts: Dict[str, ContractData] = {}

        self.active_orders: Dict[str, OrderData] = {}

        self.add_function()
        self.register_event()

        self.order_update_interval = 0  # for counting the timer.
        self.position_update_interval = 0
        self.account_update_interval = 0

    def add_function(self) -> None:
        """Add query function to main engine."""
        self.main_engine.get_tick = self.get_tick
        self.main_engine.get_position = self.get_position
        self.main_engine.get_account = self.get_account
        self.main_engine.get_contract = self.get_contract
        self.main_engine.get_all_positions = self.get_all_positions
        self.main_engine.get_all_accounts = self.get_all_accounts
        self.main_engine.get_all_contracts = self.get_all_contracts
        self.main_engine.get_all_active_orders = self.get_all_active_orders
        self.main_engine.get_active_order = self.get_active_order

    def register_event(self) -> None:
        """"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_POSITION, self.process_position_event)
        self.event_engine.register(EVENT_ACCOUNT, self.process_account_event)
        self.event_engine.register(EVENT_CONTRACT, self.process_contract_event)
        self.event_engine.register(EVENT_TIMER, self.process_timer)

    def process_tick_event(self, event: Event) -> None:
        """"""
        tick = event.data
        self.ticks[tick.vt_symbol] = tick

    def process_order_event(self, event: Event) -> None:
        """"""
        order = event.data

        # If order is active, then update data in dict.
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        # Otherwise, pop inactive order from in dict
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

    def process_position_event(self, event: Event) -> None:
        """"""
        position = event.data
        self.positions[position.vt_positionid] = position

    def process_account_event(self, event: Event) -> None:
        """"""
        account: AccountData = event.data
        self.accounts[account.vt_accountid] = account

    def process_contract_event(self, event: Event) -> None:
        """"""
        contract = event.data
        self.contracts[contract.vt_symbol] = contract

    def process_timer(self, event: Event) -> None:
        """
        update the orders, positions by timer, for we may be disconnected from server update push.
        """

        self.order_update_interval += 1
        self.position_update_interval += 1
        self.account_update_interval += 1

        if self.order_update_interval >= SETTINGS.get('order_update_interval', 120):
            self.order_update_interval = 0
            orders = self.get_all_active_orders()
            for order in orders:
                if order.datetime and (datetime.now() - order.datetime).seconds > SETTINGS.get(
                        'order_update_timer', 120):
                    req = order.create_query_request()
                    self.main_engine.query_order(req, order.gateway_name)

        if self.position_update_interval >= SETTINGS.get('position_update_interval', 120):
            self.main_engine.query_position()
            self.position_update_interval = 0

        if self.account_update_interval >= SETTINGS.get('account_update_interval', 120):
            self.account_update_interval = 0
            self.main_engine.query_account()

    def get_tick(self, vt_symbol: str) -> Optional[TickData]:
        """
        Get latest market tick data by vt_symbol.
        """
        return self.ticks.get(vt_symbol, None)

    def get_position(self, vt_positionid: str) -> Optional[PositionData]:
        """
        Get latest position data by vt_positionid.
        """
        return self.positions.get(vt_positionid, None)

    def get_account(self, vt_accountid: str) -> Optional[AccountData]:
        """
        Get latest account data by vt_accountid.
        """
        return self.accounts.get(vt_accountid, None)

    def get_contract(self, vt_symbol: str) -> Optional[ContractData]:
        """
        Get contract data by vt_symbol.
        """
        return self.contracts.get(vt_symbol, None)

    def get_all_positions(self) -> List[PositionData]:
        """
        Get all position data.
        """
        return list(self.positions.values())

    def get_all_accounts(self) -> List[AccountData]:
        """
        Get all account data.
        """
        return list(self.accounts.values())

    def get_all_contracts(self) -> List[ContractData]:
        """
        Get all contract data.
        """
        return list(self.contracts.values())

    def get_all_active_orders(self, vt_symbol: str = "") -> List[OrderData]:
        """
        Get all active orders by vt_symbol.

        If vt_symbol is empty, return all active orders.
        """
        if not vt_symbol:
            return list(self.active_orders.values())
        else:
            active_orders = [
                order
                for order in self.active_orders.values()
                if order.vt_symbol == vt_symbol
            ]
            return active_orders

    def get_active_order(self, vt_orderid) -> Optional[OrderData]:
        return self.active_orders.get(vt_orderid, None)


class CtaEngine(BaseEngine):
    """"""

    setting_filename = "grid_strategy_setting.json"
    data_filename = "grid_strategy_data.json"

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """"""
        super(CtaEngine, self).__init__(
            main_engine, event_engine, 'strategy')

        self.strategy_setting = {}  # strategy_name: dict
        self.strategy_data = {}  # strategy_name: dict

        self.classes = {}  # class_name: stategy_class
        self.strategies = {}  # strategy_name: strategy

        self.symbol_strategy_map = defaultdict(
            list)  # vt_symbol: strategy list

        self.orderid_strategy_map = {}  # vt_orderid: strategy

        self.strategy_orderid_map = defaultdict(set)  # strategy_name: orderid list

        self.init_executor = ThreadPoolExecutor(max_workers=1)

        self.vt_tradeids = set()  # for filtering duplicate trade

    def init_engine(self):
        """
        """
        self.load_strategy_class()
        self.load_strategy_setting()
        self.load_strategy_data()
        self.register_event()
        self.write_log("Strategy Engine Start Successfully.")

    def load_strategy_class(self):
        """
        Load strategy class from source code.
        """
        from .strategies.future_grid_strategy import FutureGridStrategy
        from .strategies.spot_grid_strategy import SpotGridStrategy
        self.classes[FutureGridStrategy.__name__] = FutureGridStrategy
        self.classes[SpotGridStrategy.__name__] = SpotGridStrategy

    def load_strategy_setting(self):
        """
        Load setting file.
        """
        self.strategy_setting = load_json(self.setting_filename)

        for strategy_name, strategy_config in self.strategy_setting.items():
            self.add_strategy(
                strategy_config["class_name"],
                strategy_name,
                strategy_config["vt_symbol"],
                strategy_config["setting"]
            )

    def load_strategy_data(self):
        """
        Load strategy data from json file.
        """
        self.strategy_data = load_json(self.data_filename)

    def register_event(self):
        """"""
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)

    def close(self):
        """"""
        self.stop_all_strategies()

    def process_tick_event(self, event: Event):
        """"""
        tick = event.data

        strategies = self.symbol_strategy_map[tick.vt_symbol]
        if not strategies:
            return

        for strategy in strategies:
            if strategy.inited:
                self.call_strategy_func(strategy, strategy.on_tick, tick)

    def process_order_event(self, event: Event):
        """"""
        order = event.data

        strategy = self.orderid_strategy_map.get(order.vt_orderid, None)
        if not strategy:
            return

        # Remove vt_orderid if order is no longer active.
        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        if order.vt_orderid in vt_orderids and not order.is_active():
            vt_orderids.remove(order.vt_orderid)

        # Call strategy on_order function
        self.call_strategy_func(strategy, strategy.on_order, order)

    def process_trade_event(self, event: Event):
        """"""
        trade = event.data

        # Filter duplicate trade push
        if trade.vt_tradeid in self.vt_tradeids:
            return

        self.vt_tradeids.add(trade.vt_tradeid)

        strategy = self.orderid_strategy_map.get(trade.vt_orderid, None)
        if not strategy:
            return

        # Update strategy pos before calling on_trade method
        if trade.direction == Direction.LONG:
            strategy.pos += float(trade.volume)
        else:
            strategy.pos -= float(trade.volume)

        self.call_strategy_func(strategy, strategy.on_trade, trade)

        # Sync strategy variables to data file
        self.sync_strategy_data(strategy)

        # Update GUI
        self.put_strategy_event(strategy)

    def send_order(
            self,
            strategy: CtaTemplate,
            direction: Direction,
            offset: Offset,
            price: float,
            volume: float
    ):
        """
        """
        contract = self.main_engine.get_contract(strategy.vt_symbol)
        if not contract:
            self.write_log(f"Symbol Not Found: {strategy.vt_symbol}", strategy)
            return ""

        # Round order price and volume to nearest incremental value
        price = round_to(price, contract.price_tick)
        volume = floor_to(volume, contract.min_volume)

        return self.send_limit_order(strategy, contract, direction, offset, price, volume)

    def send_limit_order(
            self,
            strategy: CtaTemplate,
            contract: ContractData,
            direction: Direction,
            offset: Offset,
            price: Decimal,
            volume: Decimal
    ):
        """
        Send a limit order to server.
        """
        return self.send_server_order(
            strategy,
            contract,
            direction,
            offset,
            price,
            volume,
            OrderType.LIMIT
        )

    def send_server_order(
            self,
            strategy: CtaTemplate,
            contract: ContractData,
            direction: Direction,
            offset: Offset,
            price: Decimal,
            volume: Decimal,
            type: OrderType
    ):
        """
        Send a new order to server.
        """
        # Create request and send order.
        original_req = OrderRequest(
            symbol=contract.symbol,
            exchange=contract.exchange,
            direction=direction,
            offset=offset,
            type=type,
            price=price,
            volume=volume,
            reference=f"{strategy.strategy_name}"
        )

        # Convert with offset converter
        # req_list = self.offset_converter.convert_order_request(original_req, lock)


        vt_orderid = self.main_engine.send_order(
            original_req, contract.gateway_name)

        # Check if sending order successful
        if not vt_orderid:
            return []

        # Save relationship between orderid and strategy.
        self.orderid_strategy_map[vt_orderid] = strategy
        self.strategy_orderid_map[strategy.strategy_name].add(vt_orderid)

        return [vt_orderid]


    def cancel_order(self, strategy: CtaTemplate, vt_orderid: str):
        """
        """
        self.cancel_server_order(strategy, vt_orderid)

    def cancel_server_order(self, strategy: CtaTemplate, vt_orderid: str):
        """
        Cancel existing order by vt_orderid.
        """
        order = self.main_engine.get_active_order(vt_orderid)
        if not order:
            self.write_log(f"Cancel Order Failed，Order Id Not Found: {vt_orderid}", strategy)
            return

        req = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)

    def cancel_all(self, strategy: CtaTemplate):
        """
        Cancel all active orders of a strategy.
        """
        vt_orderids = self.strategy_orderid_map[strategy.strategy_name]
        if not vt_orderids:
            return

        for vt_orderid in copy(vt_orderids):
            self.cancel_order(strategy, vt_orderid)

    def get_price_tick(self, strategy: CtaTemplate):
        """
        Return contract price tick data.
        """
        contract: ContractData = self.main_engine.get_contract(strategy.vt_symbol)

        if contract:
            return contract.price_tick
        else:
            return None

    def call_strategy_func(
            self, strategy: CtaTemplate, func: Callable, params: Any = None
    ):
        """
        Call function of a strategy and catch any exception raised.
        """
        try:
            if params:
                func(params)
            else:
                func()
        except Exception:
            strategy.inited = False
            strategy.trading = False

            msg = f"Strategy Error: {traceback.format_exc()}"
            sys.stderr.write(msg)

    def add_strategy(
            self, class_name: str, strategy_name: str, vt_symbol: str, setting: dict
    ):
        """
        Add a new strategy.
        """
        if strategy_name in self.strategies:
            self.write_log(f"Add Strategy Failed, {strategy_name} existed")
            return

        strategy_class = self.classes.get(class_name, None)
        if not strategy_class:
            self.write_log(f"Add Strategy Failed，Strategy Class Not Found")
            return

        strategy = strategy_class(self, strategy_name, vt_symbol, setting)
        self.strategies[strategy_name] = strategy

        # Add vt_symbol to strategy map.
        strategies = self.symbol_strategy_map[vt_symbol]
        strategies.append(strategy)

        # Update to setting file.
        self.update_strategy_setting(strategy_name, setting)

        self.put_strategy_event(strategy)

    def init_strategy(self, strategy_name: str):
        """
        Init a strategy.
        """
        self.init_executor.submit(self._init_strategy, strategy_name)

    def _init_strategy(self, strategy_name: str):
        """
        Init strategies in queue.
        """
        strategy = self.strategies[strategy_name]

        if strategy.inited:
            self.write_log(f"{strategy_name} Already Initialized")
            return

        self.write_log(f"{strategy_name} Start Initialized")

        # Call on_init function of strategy
        self.call_strategy_func(strategy, strategy.on_init)

        # Restore strategy data(variables)
        data = self.strategy_data.get(strategy_name, None)
        if data:
            for name in strategy.variables:
                value = data.get(name, None)
                if value:
                    setattr(strategy, name, value)

        # Subscribe market data
        contract = self.main_engine.get_contract(strategy.vt_symbol)
        if contract:
            req = SubscribeRequest(
                symbol=contract.symbol, exchange=contract.exchange)
            self.main_engine.subscribe(req, contract.gateway_name)
        else:
            self.write_log(f"Subscribe Market Data Failed，Symbol Not Found {strategy.vt_symbol}", strategy)

        # Put event to update init completed status.
        strategy.inited = True
        self.put_strategy_event(strategy)
        self.write_log(f"{strategy_name} Initialized.")

    def start_strategy(self, strategy_name: str):
        """
        Start a strategy.
        """
        strategy = self.strategies[strategy_name]
        if not strategy.inited:
            self.write_log(f"Strategy {strategy.strategy_name} Start Failed，Please Init First.")
            return

        if strategy.trading:
            self.write_log(f"{strategy_name} Already Start.")
            return

        self.call_strategy_func(strategy, strategy.on_start)
        strategy.trading = True

        self.put_strategy_event(strategy)

    def stop_strategy(self, strategy_name: str):
        """
        Stop a strategy.
        """
        strategy = self.strategies[strategy_name]
        if not strategy.trading:
            return

        # Call on_stop function of the strategy
        self.call_strategy_func(strategy, strategy.on_stop)

        # Change trading status of strategy to False
        strategy.trading = False

        # Cancel all orders of the strategy
        self.cancel_all(strategy)

        # Sync strategy variables to data file
        self.sync_strategy_data(strategy)

        # Update GUI
        self.put_strategy_event(strategy)

    def edit_strategy(self, strategy_name: str, setting: dict):
        """
        Edit parameters of a strategy.
        """
        strategy = self.strategies[strategy_name]
        strategy.update_setting(setting)

        self.update_strategy_setting(strategy_name, setting)
        self.put_strategy_event(strategy)

    def remove_strategy(self, strategy_name: str):
        """
        Remove a strategy.
        """
        strategy = self.strategies[strategy_name]
        if strategy.trading:
            self.write_log(f"Strategy {strategy.strategy_name} Remove Failed，Please Stop First.")
            return

        # Remove setting
        self.remove_strategy_setting(strategy_name)

        # Remove from symbol strategy map
        strategies = self.symbol_strategy_map[strategy.vt_symbol]
        strategies.remove(strategy)

        # Remove from active orderid map
        if strategy_name in self.strategy_orderid_map:
            vt_orderids = self.strategy_orderid_map.pop(strategy_name)

            # Remove vt_orderid strategy map
            for vt_orderid in vt_orderids:
                if vt_orderid in self.orderid_strategy_map:
                    self.orderid_strategy_map.pop(vt_orderid)

        # Remove from strategies
        self.strategies.pop(strategy_name)

        return True

    def sync_strategy_data(self, strategy: CtaTemplate):
        """
        Sync strategy data into json file.
        """
        data = strategy.get_variables()
        data.pop("inited")  # Strategy status (inited, trading) should not be synced.
        data.pop("trading")

        self.strategy_data[strategy.strategy_name] = data
        save_json(self.data_filename, self.strategy_data)

    def get_all_strategy_class_names(self):
        """
        Return names of strategy classes loaded.
        """
        return list(self.classes.keys())

    def get_strategy_class_parameters(self, class_name: str):
        """
        Get default parameters of a strategy class.
        """
        strategy_class = self.classes[class_name]

        parameters = {}
        for name in strategy_class.parameters:
            parameters[name] = getattr(strategy_class, name)

        return parameters

    def get_strategy_parameters(self, strategy_name):
        """
        Get parameters of a strategy.
        """
        strategy = self.strategies[strategy_name]
        return strategy.get_parameters()

    def init_all_strategies(self):
        """
        """
        for strategy_name in self.strategies.keys():
            self.init_strategy(strategy_name)

    def start_all_strategies(self):
        """
        """
        for strategy_name in self.strategies.keys():
            self.start_strategy(strategy_name)

    def stop_all_strategies(self):
        """
        """
        for strategy_name in self.strategies.keys():
            self.stop_strategy(strategy_name)

    def update_strategy_setting(self, strategy_name: str, setting: dict):
        """
        Update setting file.
        """
        strategy = self.strategies[strategy_name]

        self.strategy_setting[strategy_name] = {
            "class_name": strategy.__class__.__name__,
            "vt_symbol": strategy.vt_symbol,
            "setting": setting,
        }
        save_json(self.setting_filename, self.strategy_setting)

    def remove_strategy_setting(self, strategy_name: str):
        """
        Update setting file.
        """
        if strategy_name not in self.strategy_setting:
            return

        self.strategy_setting.pop(strategy_name)
        save_json(self.setting_filename, self.strategy_setting)

    def put_strategy_event(self, strategy: CtaTemplate):
        """
        Put an event to update strategy status.
        """
        data = strategy.get_data()
        event = Event(EVENT_CTA_STRATEGY, data)
        self.event_engine.put(event)

    def write_log(self, msg: str, strategy: CtaTemplate = None):
        """
        Create cta engine log event.
        """
        if strategy:
            msg = f"{strategy.strategy_name}: {msg}"

        log = LogData(msg=msg, gateway_name='cta')
        event = Event(type=EVENT_LOG, data=log)
        self.event_engine.put(event)
