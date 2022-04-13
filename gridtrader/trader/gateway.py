"""

"""

from abc import ABC, abstractmethod
from typing import Any, Sequence, Dict, List
import uuid

from gridtrader.event import Event, EventEngine
from gridtrader.event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
)
from .object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    LogData,
    OrderRequest,
    CancelRequest,
    QueryRequest,
    SubscribeRequest,
    Exchange
)


class BaseGateway(ABC):
    """
    Abstract gateway class for creating gateways connection
    to different trading systems.

    # How to implement a gateway:

    ---
    ## Basics
    A gateway should satisfies:
    * this class should be thread-safe:
        * all methods should be thread-safe
        * no mutable shared properties between objects.
    * all methods should be non-blocked
    * satisfies all requirements written in docstring for every method and callbacks.
    * automatically reconnect if connection lost.

    ---
    ## methods must implements:
    all @abstractmethod

    ---
    ## callbacks must response manually:
    * on_tick
    * on_trade
    * on_order
    * on_position
    * on_account
    * on_contract

    All the XxxData passed to callback should be constant, which means that
        the object should not be modified after passing to on_xxxx.
    So if you use a cache to store reference of data, use copy.copy to create a new object
    before passing that data into on_xxxx



    """

    # Fields required in setting dict for connect function.
    default_setting: Dict[str, Any] = {}

    # Exchanges supported in the gateway.
    exchanges: List[Exchange] = []

    def __init__(self, event_engine: EventEngine, gateway_name: str):
        """"""
        self.event_engine: EventEngine = event_engine
        self.gateway_name: str = gateway_name
        self.active_orders: Dict[str, OrderData] = {}  # {order_id: OrderData} for updating the trade event

    def on_event(self, type: str, data: Any = None) -> None:
        """
        General event push.
        """
        event = Event(type, data)
        self.event_engine.put(event)

    def on_tick(self, tick: TickData) -> None:
        """
        Tick event push.
        Tick event of a specific vt_symbol is also pushed.
        """
        self.on_event(EVENT_TICK, tick)
        self.on_event(EVENT_TICK + tick.vt_symbol, tick)

    def on_trade(self, trade: TradeData) -> None:
        """
        Trade event push.
        Trade event of a specific vt_symbol is also pushed.
        """
        self.on_event(EVENT_TRADE, trade)
        self.on_event(EVENT_TRADE + trade.vt_symbol, trade)

    def on_order(self, order: OrderData) -> None:
        """
        Order event push.
        Order event of a specific vt_orderid is also pushed.
        """
        self.on_event(EVENT_ORDER, order)
        self.on_event(EVENT_ORDER + order.vt_orderid, order)

        # for updating the trade event
        pre_order = self.active_orders.get(order.vt_orderid, None)

        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

        if order.trade_data:
            self.on_trade(order.trade_data)
        elif pre_order:
            trade_volume = order.traded - pre_order.traded
            if trade_volume > 0:
                trade = TradeData(
                    symbol=order.symbol,
                    exchange=order.exchange,
                    orderid=order.orderid,
                    tradeid=str(uuid.uuid1()),
                    direction=order.direction,
                    price=order.price,
                    volume=trade_volume,
                    datetime=order.datetime,
                    gateway_name=self.gateway_name,
                )
                self.on_trade(trade)

    def on_position(self, position: PositionData) -> None:
        """
        Position event push.
        Position event of a specific vt_symbol is also pushed.
        """
        self.on_event(EVENT_POSITION, position)
        self.on_event(EVENT_POSITION + position.vt_symbol, position)

    def on_account(self, account: AccountData) -> None:
        """
        Account event push.
        Account event of a specific vt_accountid is also pushed.
        """
        self.on_event(EVENT_ACCOUNT, account)
        self.on_event(EVENT_ACCOUNT + account.vt_accountid, account)

    def on_log(self, log: LogData) -> None:
        """
        Log event push.
        """
        self.on_event(EVENT_LOG, log)

    def on_contract(self, contract: ContractData) -> None:
        """
        Contract event push.
        """
        self.on_event(EVENT_CONTRACT, contract)

    def write_log(self, msg: str) -> None:
        """
        Write a log event from gateway.
        """
        log = LogData(msg=msg, gateway_name=self.gateway_name)
        self.on_log(log)

    @abstractmethod
    def connect(self, setting: dict) -> None:
        """
        Start gateway connection.

        to implement this method, you must:
        * connect to server if necessary
        * log connected if all necessary connection is established
        * do the following query and response corresponding on_xxxx and write_log
            * contracts : on_contract
            * account asset : on_account
            * account holding: on_position
            * orders of account: on_order
            * trades of account: on_trade
        * if any of query above is failed,  write log.

        future plan:
        response callback/change status instead of write_log

        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close gateway connection.
        """
        pass

    @abstractmethod
    def subscribe(self, req: SubscribeRequest) -> None:
        """
        Subscribe tick data update.
        """
        pass

    @abstractmethod
    def send_order(self, req: OrderRequest) -> str:
        """
        Send a new order to server.

        implementation should finish the tasks blow:
        * create an OrderData from req using OrderRequest.create_order_data
        * assign a unique(gateway instance scope) id to OrderData.orderid
        * send request to server
            * if request is sent, OrderData.status should be set to Status.SUBMITTING
            * if request is failed to sent, OrderData.status should be set to Status.REJECTED
        * response on_order:
        * return vt_orderid

        :return str vt_orderid for created OrderData
        """
        pass

    @abstractmethod
    def cancel_order(self, req: CancelRequest) -> None:
        """
        Cancel an existing order.
        implementation should finish the tasks blow:
        * send request to server
        """
        pass

    @abstractmethod
    def query_order(self, req: QueryRequest) -> None:
        """
        query an existing order.
        implementation should finish the tasks blow:
        * send request to server
        """
        pass

    def send_orders(self, reqs: Sequence[OrderRequest]) -> List[str]:
        """
        Send a batch of orders to server.
        Use a for loop of send_order function by default.
        Reimplement this function if batch order supported on server.
        """
        vt_orderids = []

        for req in reqs:
            vt_orderid = self.send_order(req)
            vt_orderids.append(vt_orderid)

        return vt_orderids

    def cancel_orders(self, reqs: Sequence[CancelRequest]) -> None:
        """
        Cancel a batch of orders to server.
        Use a for loop of cancel_order function by default.
        Reimplement this function if batch cancel supported on server.
        """
        for req in reqs:
            self.cancel_order(req)

    @abstractmethod
    def query_account(self) -> None:
        """
        Query account balance.
        """
        pass

    @abstractmethod
    def query_position(self) -> None:
        """
        Query holding positions.
        """
        pass


    def get_default_setting(self) -> Dict[str, Any]:
        """
        Return default setting dict.
        """
        return self.default_setting