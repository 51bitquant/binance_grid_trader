"""
Gateway for Binance Crypto Exchange.
"""

import urllib
import hashlib
import hmac
import time
from copy import copy
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Dict, Tuple
from decimal import Decimal

from gridtrader.api.rest import RestClient, Request
from gridtrader.api.websocket import WebsocketClient
from gridtrader.trader.constant import (
    Direction,
    Exchange,
    Product,
    Status,
    OrderType,
    Offset
)
from gridtrader.trader.gateway import BaseGateway
from gridtrader.trader.object import (
    TickData,
    OrderData,
    TradeData,
    AccountData,
    ContractData,
    PositionData,
    OrderRequest,
    QueryRequest,
    CancelRequest,
    SubscribeRequest,
)
from gridtrader.event import EVENT_TIMER, Event, EventEngine

F_REST_HOST: str = "https://fapi.binance.com"
F_WEBSOCKET_TRADE_HOST: str = "wss://fstream.binance.com/ws/"
F_WEBSOCKET_DATA_HOST: str = "wss://fstream.binance.com/stream?streams="

D_REST_HOST: str = "https://dapi.binance.com"
D_WEBSOCKET_TRADE_HOST: str = "wss://dstream.binance.com/ws/"
D_WEBSOCKET_DATA_HOST: str = "wss://dstream.binance.com/stream?streams="

STATUS_BINANCES2VT: Dict[str, Status] = {
    "NEW": Status.NOTTRADED,
    "PARTIALLY_FILLED": Status.PARTTRADED,
    "FILLED": Status.ALLTRADED,
    "CANCELED": Status.CANCELLED,
    "REJECTED": Status.REJECTED,
    "EXPIRED": Status.CANCELLED
}

ORDERTYPE_VT2BINANCES: Dict[OrderType, Tuple[str, str]] = {
    OrderType.LIMIT: ("LIMIT", "GTC"),
    OrderType.MARKET: ("MARKET", "GTC"),
    OrderType.FAK: ("LIMIT", "IOC"),
    OrderType.FOK: ("LIMIT", "FOK"),
    OrderType.LIMIT_MAKER: ("LIMIT", "GTX")
}
ORDERTYPE_BINANCES2VT: Dict[Tuple[str, str], OrderType] = {v: k for k, v in ORDERTYPE_VT2BINANCES.items()}

DIRECTION_VT2BINANCES: Dict[Direction, str] = {
    Direction.LONG: "BUY",
    Direction.SHORT: "SELL"
}
DIRECTION_BINANCES2VT: Dict[str, Direction] = {v: k for k, v in DIRECTION_VT2BINANCES.items()}


class Security(Enum):
    NONE: int = 0
    SIGNED: int = 1
    API_KEY: int = 2


symbol_name_map: Dict[str, str] = {}


class BinancesGateway(BaseGateway):
    """
    Trader Gateway for Binance connection.
    """

    default_setting = {
        "key": "",
        "secret": "",
        "futures_type": ["USDT", "COIN"],
        "proxy_host": "",
        "proxy_port": 0,
    }

    exchanges: Exchange = [Exchange.BINANCE]

    def __init__(self, event_engine: EventEngine):
        """Constructor"""
        super().__init__(event_engine, "Futures")

        self.trade_ws_api = BinancesTradeWebsocketApi(self)
        self.market_ws_api = BinancesDataWebsocketApi(self)
        self.rest_api = BinancesRestApi(self)

    def connect(self, setting: dict) -> None:
        """"""
        key = setting["key"]
        secret = setting["secret"]
        proxy_host = setting["proxy_host"] if setting["proxy_host"] else ""
        proxy_port = int(setting["proxy_port"]) if setting["proxy_port"] else 0
        futures_type = setting["futures_type"] if setting["futures_type"] else "USDT"

        if futures_type == "USDT":
            usdt_base = True
        else:
            usdt_base = False

        self.rest_api.connect(usdt_base, key, secret, proxy_host, proxy_port)
        self.market_ws_api.connect(usdt_base, proxy_host, proxy_port)

        self.event_engine.register(EVENT_TIMER, self.process_timer_event)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        self.market_ws_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """"""
        return self.rest_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        self.rest_api.cancel_order(req)

    def query_order(self, req: QueryRequest):
        self.rest_api.query_order(req)

    def query_account(self) -> None:
        """"""
        self.rest_api.query_account()

    def query_position(self) -> None:
        """"""
        self.rest_api.query_position()

    def close(self) -> None:
        """"""
        self.rest_api.stop()
        self.trade_ws_api.stop()
        self.market_ws_api.stop()

    def process_timer_event(self, event: Event) -> None:
        """"""
        self.rest_api.keep_user_stream()


class BinancesRestApi(RestClient):
    """
    BINANCE Future REST API
    """

    def __init__(self, gateway: BinancesGateway):
        """"""
        super().__init__()

        self.gateway: BinancesGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.trade_ws_api: BinancesTradeWebsocketApi = self.gateway.trade_ws_api
        self.market_ws_api: BinancesDataWebsocketApi = self.gateway.market_ws_api

        self.key: str = ""
        self.secret: str = ""

        self.user_stream_key: str = ""
        self.keep_alive_count: int = 0
        self.recv_window: int = 5000
        self.time_offset: int = 0

        self.order_count: int = 1_000_000
        self.order_count_lock: Lock = Lock()
        self.connect_time: int = 0
        self.usdt_base: bool = False

    def sign(self, request: Request) -> Request:
        """
        Generate BINANCE signature.
        """
        security = request.data["security"]
        if security == Security.NONE:
            request.data = None
            return request

        if request.params:
            path = request.path + "?" + urllib.parse.urlencode(request.params)
        else:
            request.params = dict()
            path = request.path

        if security == Security.SIGNED:
            timestamp = int(time.time() * 1000)

            if self.time_offset > 0:
                timestamp -= abs(self.time_offset)
            elif self.time_offset < 0:
                timestamp += abs(self.time_offset)

            request.params["timestamp"] = timestamp

            query = urllib.parse.urlencode(sorted(request.params.items()))
            signature = hmac.new(self.secret, query.encode(
                "utf-8"), hashlib.sha256).hexdigest()

            query += "&signature={}".format(signature)
            path = request.path + "?" + query

        request.path = path
        request.params = {}
        request.data = {}

        # Add headers
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "X-MBX-APIKEY": self.key
        }

        if security in [Security.SIGNED, Security.API_KEY]:
            request.headers = headers

        return request

    def connect(
            self,
            usdt_base: bool,
            key: str,
            secret: str,
            proxy_host: str,
            proxy_port: int
    ) -> None:
        """
        Initialize connection to REST server.
        """
        self.usdt_base = usdt_base
        self.key = key
        self.secret = secret.encode()
        self.proxy_port = proxy_port
        self.proxy_host = proxy_host
        self.connect_time = (
                int(datetime.now().strftime("%y%m%d%H%M%S")) * self.order_count
        )

        if self.usdt_base:
            self.init(F_REST_HOST, proxy_host, proxy_port)
        else:
            self.init(D_REST_HOST, proxy_host, proxy_port)

        self.start(3)

        self.gateway.write_log("Connect Futures REST API")

        self.query_time()
        self.set_position_side()
        self.query_account()
        self.query_position()
        self.query_orders()
        self.query_contract()
        self.start_user_stream()

    def query_time(self) -> Request:
        """"""
        data = {
            "security": Security.NONE
        }

        if self.usdt_base:
            path = "/fapi/v1/time"
        else:
            path = "/dapi/v1/time"

        return self.add_request(
            "GET",
            path,
            callback=self.on_query_time,
            data=data
        )

    def query_account(self) -> Request:
        """"""
        data = {"security": Security.SIGNED}

        if self.usdt_base:
            path = "/fapi/v1/account"
        else:
            path = "/dapi/v1/account"

        self.add_request(
            method="GET",
            path=path,
            callback=self.on_query_account,
            data=data
        )

    def set_position_side(self) -> Request:
        data = {"security": Security.SIGNED}

        params = {
            "dualSidePosition": False
        }

        if self.usdt_base:
            path = "/fapi/v1/positionSide/dual"
        else:
            path = "/dapi/v1/positionSide/dual"
        self.add_request(
            method="POST",
            path=path,
            params=params,
            callback=self.on_set_position_side,
            data=data
        )

    def on_set_position_side(self, data: dict, request: Request) -> None:
        """"""
        pass

    def query_position(self) -> Request:
        """"""
        data = {"security": Security.SIGNED}

        if self.usdt_base:
            path = "/fapi/v2/positionRisk"
        else:
            path = "/dapi/v1/positionRisk"

        self.add_request(
            method="GET",
            path=path,
            callback=self.on_query_position,
            data=data
        )

    def query_orders(self) -> None:
        """"""
        data = {"security": Security.SIGNED}

        if self.usdt_base:
            path = "/fapi/v1/openOrders"
        else:
            path = "/dapi/v1/openOrders"

        self.add_request(
            method="GET",
            path=path,
            callback=self.on_query_orders,
            data=data
        )

    def query_order(self, req: QueryRequest) -> None:
        """"""
        data = {
            "security": Security.SIGNED
        }

        params = {
            "symbol": req.symbol,
            "origClientOrderId": req.orderid
        }

        if self.usdt_base:
            path = "/fapi/v1/order"
        else:
            path = "/dapi/v1/order"

        self.add_request(
            method="GET",
            path=path,
            callback=self.on_query_order,
            params=params,
            data=data,
            extra=req
        )

    def query_contract(self) -> Request:
        """"""
        data = {
            "security": Security.NONE
        }

        if self.usdt_base:
            path = "/fapi/v1/exchangeInfo"
        else:
            path = "/dapi/v1/exchangeInfo"

        self.add_request(
            method="GET",
            path=path,
            callback=self.on_query_contract,
            data=data
        )

    def _new_order_id(self) -> int:
        """"""
        with self.order_count_lock:
            self.order_count += 1
            return self.order_count

    def send_order(self, req: OrderRequest) -> str:
        """"""
        orderid = "x-cLbi5uMH" + str(self.connect_time + self._new_order_id())
        order = req.create_order_data(
            orderid,
            self.gateway_name
        )
        self.gateway.on_order(order)

        data = {
            "security": Security.SIGNED
        }

        order_type, time_condition = ORDERTYPE_VT2BINANCES[req.type]

        params = {
            "symbol": req.symbol,
            "side": DIRECTION_VT2BINANCES[req.direction],
            "type": order_type,
            "timeInForce": time_condition,
            "price": req.price,
            "quantity": req.volume,
            "newClientOrderId": orderid,
        }

        if req.offset == Offset.CLOSE:
            params["reduceOnly"] = True

        if self.usdt_base:
            path = "/fapi/v1/order"
        else:
            path = "/dapi/v1/order"

        self.add_request(
            method="POST",
            path=path,
            callback=self.on_send_order,
            data=data,
            params=params,
            extra=order,
            on_error=self.on_send_order_error,
            on_failed=self.on_send_order_failed
        )

        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        data = {
            "security": Security.SIGNED
        }

        params = {
            "symbol": req.symbol,
            "origClientOrderId": req.orderid
        }

        if self.usdt_base:
            path = "/fapi/v1/order"
        else:
            path = "/dapi/v1/order"

        self.add_request(
            method="DELETE",
            path=path,
            callback=self.on_cancel_order,
            params=params,
            data=data,
            extra=req
        )

    def start_user_stream(self) -> None:
        """"""
        data = {
            "security": Security.API_KEY
        }

        if self.usdt_base:
            path = "/fapi/v1/listenKey"
        else:
            path = "/dapi/v1/listenKey"

        self.add_request(
            method="POST",
            path=path,
            callback=self.on_start_user_stream,
            data=data
        )

    def keep_user_stream(self) -> Request:
        """"""
        self.keep_alive_count += 1
        if self.keep_alive_count < 600:
            return
        self.keep_alive_count = 0

        data = {
            "security": Security.API_KEY
        }

        params = {
            "listenKey": self.user_stream_key
        }

        if self.usdt_base:
            path = "/fapi/v1/listenKey"
        else:
            path = "/dapi/v1/listenKey"
        self.add_request(
            method="PUT",
            path=path,
            callback=self.on_keep_user_stream,
            params=params,
            data=data
        )

    def on_query_time(self, data: dict, request: Request) -> None:
        """"""
        local_time = int(time.time() * 1000)
        server_time = int(data["serverTime"])
        self.time_offset = local_time - server_time

    def on_query_account(self, data: dict, request: Request) -> None:
        """"""
        for asset in data["assets"]:
            account = AccountData(
                accountid=asset["asset"],
                balance=float(asset["walletBalance"]),
                frozen=float(asset["maintMargin"]),
                gateway_name=self.gateway_name
            )

            # if account.balance:
            self.gateway.on_account(account)

        self.gateway.write_log("Query Futures Account Successfully.")

    def on_query_position(self, data: list, request: Request) -> None:
        """
        Query position.
        """
        # symbols = self.market_ws_api.ticks.keys()

        for d in data:
            if d['positionSide'] == "BOTH":
                position = PositionData(
                    symbol=d["symbol"],
                    exchange=Exchange.BINANCE,
                    direction=Direction.NET,
                    volume=Decimal(d["positionAmt"]),
                    price=Decimal(d["entryPrice"]),
                    pnl=Decimal(d["unRealizedProfit"]),
                    gateway_name=self.gateway_name,
                )

                # if position.volume or d['symbol'].lower() in symbols:
                self.gateway.on_position(position)

    def on_query_orders(self, data: dict, request: Request) -> None:
        """"""
        for d in data:
            key = (d["type"], d["timeInForce"])
            order_type = ORDERTYPE_BINANCES2VT.get(key, None)
            if not order_type:
                continue

            order = OrderData(
                orderid=d["clientOrderId"],
                symbol=d["symbol"],
                exchange=Exchange.BINANCE,
                price=Decimal(d["price"]),
                volume=Decimal(d["origQty"]),
                type=order_type,
                direction=DIRECTION_BINANCES2VT[d["side"]],
                traded=Decimal(d["executedQty"]),
                status=STATUS_BINANCES2VT.get(d["status"], None),
                datetime=generate_datetime(d["time"]),
                gateway_name=self.gateway_name,
            )
            self.gateway.on_order(order)

        self.gateway.write_log("Query Futures Orders Successfully.")

    def on_query_order(self, data: dict, request: Request) -> None:
        """"""

        key = (data["type"], data["timeInForce"])
        order_type = ORDERTYPE_BINANCES2VT.get(key, None)
        if not order_type:
            return

        order = OrderData(
            orderid=data["clientOrderId"],
            symbol=data["symbol"],
            exchange=Exchange.BINANCE,
            price=Decimal(data["price"]),
            volume=Decimal(data["origQty"]),
            type=order_type,
            direction=DIRECTION_BINANCES2VT[data["side"]],
            traded=Decimal(data["executedQty"]),
            status=STATUS_BINANCES2VT.get(data["status"], None),
            datetime=generate_datetime(data["time"]),
            gateway_name=self.gateway_name,
        )
        self.gateway.on_order(order)

    def on_query_contract(self, data: dict, request: Request) -> None:
        """"""
        for d in data["symbols"]:
            base_currency = d["baseAsset"]
            quote_currency = d["quoteAsset"]
            name = f"{base_currency.upper()}/{quote_currency.upper()}"

            price_tick = Decimal("1")
            min_volume = Decimal("1")

            for f in d["filters"]:
                if f["filterType"] == "PRICE_FILTER":
                    price_tick = Decimal(f["tickSize"])
                elif f["filterType"] == "LOT_SIZE":
                    min_volume = Decimal(f["stepSize"])

            contract = ContractData(
                symbol=d["symbol"],
                exchange=Exchange.BINANCE,
                name=name,
                price_tick=price_tick,
                min_volume=min_volume,
                product=Product.FUTURES,
                gateway_name=self.gateway_name,
            )
            self.gateway.on_contract(contract)

            symbol_name_map[contract.symbol] = contract.name

        self.gateway.write_log("Query Futures Info Successfully.")

    def on_send_order(self, data: dict, request: Request) -> None:
        """"""
        pass

    def on_send_order_failed(self, status_code: str, request: Request) -> None:
        """
        Callback when sending order failed on server.
        """
        order = request.extra
        order.status = Status.REJECTED
        self.gateway.on_order(order)

        msg = f"Order Failed，Code: {status_code}, Msg：{request.response.text}"
        self.gateway.write_log(msg)

    def on_send_order_error(
            self, exception_type: type, exception_value: Exception, tb, request: Request
    ) -> None:
        """
        Callback when sending order caused exception.
        """
        order = request.extra
        order.status = Status.REJECTED
        self.gateway.on_order(order)

        # Record exception if not ConnectionError
        if not issubclass(exception_type, ConnectionError):
            self.on_error(exception_type, exception_value, tb, request)

    def on_cancel_order(self, data: dict, request: Request) -> None:
        """"""
        pass

    def on_start_user_stream(self, data: dict, request: Request) -> None:
        """"""
        self.user_stream_key = data["listenKey"]
        self.keep_alive_count = 0

        url = F_WEBSOCKET_TRADE_HOST + self.user_stream_key
        if not self.usdt_base:
            url = D_WEBSOCKET_TRADE_HOST + self.user_stream_key

        self.trade_ws_api.connect(url, self.proxy_host, self.proxy_port)

    def on_keep_user_stream(self, data: dict, request: Request) -> None:
        """"""
        pass


class BinancesTradeWebsocketApi(WebsocketClient):
    """"""

    def __init__(self, gateway: BinancesGateway):
        """"""
        super().__init__()

        self.gateway: BinancesGateway = gateway
        self.gateway_name: str = gateway.gateway_name

    def connect(self, url: str, proxy_host: str, proxy_port: int) -> None:
        """"""
        self.init(url, proxy_host, proxy_port)
        self.start()

    def on_connected(self) -> None:
        """"""
        self.gateway.write_log("Connect Futures Trade Websocket API")

    def on_packet(self, packet: dict) -> None:  # type: (dict)->None
        """"""
        if packet["e"] == "ACCOUNT_UPDATE":
            self.on_account(packet)
        elif packet["e"] == "ORDER_TRADE_UPDATE":
            self.on_order(packet)

    def on_account(self, packet: dict) -> None:
        """"""
        for acc_data in packet["a"]["B"]:
            account = AccountData(
                accountid=acc_data["a"],
                balance=float(acc_data["wb"]),
                frozen=float(acc_data["wb"]) - float(acc_data["cw"]),
                gateway_name=self.gateway_name
            )

            # if account.balance:
            self.gateway.on_account(account)

        for pos_data in packet["a"]["P"]:

            if pos_data['ps'] == "BOTH":
                position = PositionData(
                    symbol=pos_data["s"],
                    exchange=Exchange.BINANCE,
                    direction=Direction.NET,
                    volume=Decimal(pos_data["pa"]),
                    price=Decimal(pos_data["ep"]),
                    pnl=Decimal(pos_data["up"]),
                    gateway_name=self.gateway_name,
                )
                self.gateway.on_position(position)

    def on_order(self, packet: dict) -> None:
        """"""
        ord_data = packet["o"]
        key = (ord_data["o"], ord_data["f"])
        order_type = ORDERTYPE_BINANCES2VT.get(key, None)
        if not order_type:
            return

        order = OrderData(
            symbol=ord_data["s"],
            exchange=Exchange.BINANCE,
            orderid=str(ord_data["c"]),
            type=order_type,
            direction=DIRECTION_BINANCES2VT[ord_data["S"]],
            price=Decimal(ord_data["p"]),
            volume=Decimal(ord_data["q"]),
            traded=Decimal(ord_data["z"]),
            status=STATUS_BINANCES2VT[ord_data["X"]],
            datetime=generate_datetime(packet["E"]),
            gateway_name=self.gateway_name
        )

        # Push trade event
        trade_volume = Decimal(ord_data["l"])
        if trade_volume:
            trade_data = TradeData(
                symbol=order.symbol,
                exchange=order.exchange,
                orderid=order.orderid,
                tradeid=ord_data["t"],
                direction=order.direction,
                price=Decimal(ord_data["L"]),
                volume=trade_volume,
                datetime=generate_datetime(ord_data["T"]),
                gateway_name=self.gateway_name,
            )
            order.trade_data = trade_data

        else:
            order.trade_data = None

        self.gateway.on_order(order)


class BinancesDataWebsocketApi(WebsocketClient):
    """"""

    def __init__(self, gateway: BinancesGateway):
        """"""
        super().__init__()

        self.gateway: BinancesGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.ticks: Dict[str, TickData] = {}
        self.usdt_base = False

    def connect(
            self,
            usdt_base: bool,
            proxy_host: str,
            proxy_port: int,
    ) -> None:
        """"""
        self.usdt_base = usdt_base
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    def on_connected(self) -> None:
        """"""
        self.gateway.write_log("Connect Futures Market Websocket API")

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        if req.symbol not in symbol_name_map:
            self.gateway.write_log(f"Symbol Error: {req.symbol}")
            return

        # Create tick buf data
        tick = TickData(
            symbol=req.symbol,
            name=symbol_name_map.get(req.symbol, ""),
            exchange=Exchange.BINANCE,
            datetime=datetime.now(),
            gateway_name=self.gateway_name,
        )
        self.ticks[req.symbol.lower()] = tick

        # Close previous connection
        if self._active:
            self.stop()
            self.join()

        # Create new connection
        channels = []
        for ws_symbol in self.ticks.keys():
            channels.append(ws_symbol + "@depth5")

        url = F_WEBSOCKET_DATA_HOST + "/".join(channels)
        if not self.usdt_base:
            url = D_WEBSOCKET_DATA_HOST + "/".join(channels)

        self.init(url, self.proxy_host, self.proxy_port)
        self.start()

    def on_packet(self, packet: dict) -> None:
        """"""
        stream = packet["stream"]
        data = packet["data"]

        symbol, channel = stream.split("@")
        tick: TickData = self.ticks[symbol]

        bids = data["b"]
        for n in range(min(5, len(bids))):
            price, volume = bids[n]
            tick.__setattr__("bid_price_" + str(n + 1), Decimal(price))
            tick.__setattr__("bid_volume_" + str(n + 1), Decimal(volume))

        asks = data["a"]
        for n in range(min(5, len(asks))):
            price, volume = asks[n]
            tick.__setattr__("ask_price_" + str(n + 1), Decimal(price))
            tick.__setattr__("ask_volume_" + str(n + 1), Decimal(volume))

        self.gateway.on_tick(copy(tick))


def generate_datetime(timestamp: float) -> datetime:
    """"""
    dt = datetime.fromtimestamp(timestamp / 1000)
    # dt = CHINA_TZ.localize(dt)
    return dt
