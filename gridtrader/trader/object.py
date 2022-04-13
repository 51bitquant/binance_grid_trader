"""
Basic data structure used for general trading function in Binance Grid Trader.
"""

from dataclasses import dataclass
from datetime import datetime
from logging import INFO
from decimal import Decimal
from .constant import Direction, Exchange, Offset, Status, Product, OrderType

ACTIVE_STATUSES = set([Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED])


@dataclass
class BaseData:
    """
    Any data object needs a gateway_name as source
    and should inherit base data.
    """

    gateway_name: str


@dataclass
class TickData(BaseData):
    """
    Tick data contains information about:
        * last trade in market
        * orderbook snapshot
        * intraday market statistics.
    """

    symbol: str
    exchange: Exchange
    datetime: datetime

    name: str = ""

    bid_price_1: Decimal = Decimal("0")
    bid_price_2: Decimal = Decimal("0")
    bid_price_3: Decimal = Decimal("0")
    bid_price_4: Decimal = Decimal("0")
    bid_price_5: Decimal = Decimal("0")

    ask_price_1: Decimal = Decimal("0")
    ask_price_2: Decimal = Decimal("0")
    ask_price_3: Decimal = Decimal("0")
    ask_price_4: Decimal = Decimal("0")
    ask_price_5: Decimal = Decimal("0")

    bid_volume_1: Decimal = Decimal("0")
    bid_volume_2: Decimal = Decimal("0")
    bid_volume_3: Decimal = Decimal("0")
    bid_volume_4: Decimal = Decimal("0")
    bid_volume_5: Decimal = Decimal("0")

    ask_volume_1: Decimal = Decimal("0")
    ask_volume_2: Decimal = Decimal("0")
    ask_volume_3: Decimal = Decimal("0")
    ask_volume_4: Decimal = Decimal("0")
    ask_volume_5: Decimal = Decimal("0")

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

@dataclass
class OrderData(BaseData):
    """
    Order data contains information for tracking lastest status
    of a specific order.
    """

    symbol: str
    exchange: Exchange
    orderid: str

    type: OrderType = OrderType.LIMIT
    direction: Direction = None
    offset: Offset = Offset.NONE
    price: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    traded: Decimal = Decimal("0")
    status: Status = Status.SUBMITTING
    datetime: datetime = None
    reference: str = ""
    trade_data: "TradeData" = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"

    def is_active(self) -> bool:
        """
        Check if the order is active.
        """
        if self.status in ACTIVE_STATUSES:
            return True
        else:
            return False

    def create_cancel_request(self) -> "CancelRequest":
        """
        Create cancel request object from order.
        """
        req = CancelRequest(
            orderid=self.orderid, symbol=self.symbol, exchange=self.exchange
        )
        return req

    def create_query_request(self) -> "QueryRequest":
        """
        Create a query request object from order
        """
        req = QueryRequest(
            orderid=self.orderid, symbol=self.symbol, exchange=self.exchange
        )
        return req


@dataclass
class TradeData(BaseData):
    """
    Trade data contains information of a fill of an order. One order
    can have several trade fills.
    """

    symbol: str
    exchange: Exchange
    orderid: str
    tradeid: str
    direction: Direction = None

    offset: Offset = Offset.NONE
    price: Decimal = Decimal("0")
    volume: Decimal = Decimal("0")
    datetime: datetime = None

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid = f"{self.gateway_name}.{self.orderid}"
        self.vt_tradeid = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class PositionData(BaseData):
    """
    Positon data is used for tracking each individual position holding.
    """

    symbol: str
    exchange: Exchange
    direction: Direction

    volume: Decimal = 0
    frozen: Decimal = 0
    price: Decimal = 0
    pnl: Decimal = 0

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"
        self.vt_positionid = f"{self.vt_symbol}.{self.direction.value}"


@dataclass
class AccountData(BaseData):
    """
    Account data contains information about balance, frozen and
    available.
    """

    accountid: str

    balance: float = 0
    frozen: float = 0

    def __post_init__(self):
        """"""
        self.available = self.balance - self.frozen
        self.vt_accountid = f"{self.gateway_name}.{self.accountid}"


@dataclass
class LogData(BaseData):
    """
    Log data is used for recording log messages on GUI or in log files.
    """

    msg: str
    level: int = INFO

    def __post_init__(self):
        """"""
        self.time = datetime.now()


@dataclass
class ContractData(BaseData):
    """
    Contract data contains basic information about each contract traded.
    """

    symbol: str
    exchange: Exchange
    name: str
    product: Product
    price_tick: Decimal
    min_volume: Decimal = Decimal("1")  # minimum trading volume of the contract

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class SubscribeRequest:
    """
    Request sending to specific gateway for subscribing tick data update.
    """

    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderRequest:
    """
    Request sending to specific gateway for creating a new order.
    """

    symbol: str
    exchange: Exchange
    direction: Direction
    type: OrderType
    volume: Decimal
    price: Decimal = Decimal("0")
    offset: Offset = Offset.NONE
    reference: str = ""

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

    def create_order_data(self, orderid: str, gateway_name: str) -> OrderData:
        """
        Create order data from request.
        """
        order = OrderData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=orderid,
            type=self.type,
            direction=self.direction,
            offset=self.offset,
            price=self.price,
            volume=self.volume,
            reference=self.reference,
            gateway_name=gateway_name,
        )
        return order


@dataclass
class CancelRequest:
    """
    Request sending to specific gateway for canceling an existing order.
    """

    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"

@dataclass
class QueryRequest:
    """
    Request sending to specific gateway for query an existing order.
    Author: 51bitquant
    """
    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self):
        """"""
        self.vt_symbol = f"{self.symbol}.{self.exchange.value}"