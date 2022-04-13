"""
General constant string used in Trader.
"""

from enum import Enum


class Direction(Enum):
    """
    Direction of order/trade/position.
    """
    LONG = "LONG"
    SHORT = "SHORT"
    NET = "NET"


class Offset(Enum):
    """
    Offset of order/trade.
    """
    NONE = ""
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class Status(Enum):
    """
    Order status.
    """
    SUBMITTING = "SUBMITTING"
    NOTTRADED = "NOTTRADED"
    PARTTRADED = "PARTTRADED"
    ALLTRADED = "ALLTRADED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class Product(Enum):
    """
    Product class.
    """
    FUTURES = "FUTURES"
    SPOT = "SPOT"


class OrderType(Enum):
    """
    Order type.
    """
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    LIMIT_MAKER = "MAKER"
    STOP = "STOP"
    FAK = "FAK"
    FOK = "FOK"


class Exchange(Enum):
    """
    Exchange.
    """
    BINANCE = "BINANCE"


class Interval(Enum):
    """
    Interval of bar data.
    """
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"
    TICK = "tick"
