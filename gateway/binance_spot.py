
"""

    币安推荐码:  返佣10%
    https://www.binancezh.pro/cn/register?ref=AIR1GC70

    币安合约推荐码: 返佣10%
    https://www.binancezh.com/cn/futures/ref/51bitquant

    if you don't have a binance account, you can use the invitation link to register one:
    https://www.binancezh.com/cn/futures/ref/51bitquant

    or use the inviation code: 51bitquant
    网格交易: 适合币圈的高波动率的品种，适合现货， 如果交易合约，需要注意防止极端行情爆仓。


    服务器购买地址: https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing
"""


import requests
import time
import hmac
import hashlib
from enum import Enum
from threading import Lock


class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"


class RequestMethod(Enum):
    """
    请求的方法.
    """
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'


class Interval(Enum):
    """
    请求的K线数据..
    """
    MINUTE_1 = '1m'
    MINUTE_3 = '3m'
    MINUTE_5 = '5m'
    MINUTE_15 = '15m'
    MINUTE_30 = '30m'
    HOUR_1 = '1h'
    HOUR_2 = '2h'
    HOUR_4 = '4h'
    HOUR_6 = '6h'
    HOUR_8 = '8h'
    HOUR_12 = '12h'
    DAY_1 = '1d'
    DAY_3 = '3d'
    WEEK_1 = '1w'
    MONTH_1 = '1M'


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class BinanceSpotHttp(object):

    def __init__(self, api_key=None, secret=None, host=None, proxy_host=None, proxy_port=0, timeout=5, try_counts=5):
        self.api_key = api_key
        self.secret = secret
        self.host = host if host else "https://api.binance.com"
        self.recv_window = 10000
        self.timeout = timeout
        self.order_count_lock = Lock()
        self.order_count = 1_000_000
        self.try_counts = try_counts # 失败尝试的次数.
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    @property
    def proxies(self):
        if self.proxy_host and self.proxy_port:
            proxy = f"http://{self.proxy_host}:{self.proxy_port}"
            return {"http": proxy, "https": proxy}

        return None

    def build_parameters(self, params: dict):
        keys = list(params.keys())
        keys.sort()
        return '&'.join([f"{key}={params[key]}" for key in params.keys()])

    def request(self, req_method: RequestMethod, path: str, requery_dict=None, verify=False):
        url = self.host + path

        if verify:
            query_str = self._sign(requery_dict)
            url += '?' + query_str
        elif requery_dict:
            url += '?' + self.build_parameters(requery_dict)
        headers = {"X-MBX-APIKEY": self.api_key}
        for i in range(0, self.try_counts):
            try:
                response = requests.request(req_method.value, url=url, headers=headers, timeout=self.timeout, proxies=self.proxies)
                if response.status_code == 200:
                    return response.json()
                else:
                    print(response.json(), response.status_code)
            except Exception as error:
                print(f"请求:{path}, 发生了错误: {error}")
                time.sleep(3)
        return None

    def get_server_time(self):
        path = '/api/v3/time'
        return self.request(req_method=RequestMethod.GET, path=path)

    def get_exchange_info(self):

        """
        return:
         the exchange info in json format:
        {'timezone': 'UTC', 'serverTime': 1570802268092, 'rateLimits':
        [{'rateLimitType': 'REQUEST_WEIGHT', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200},
        {'rateLimitType': 'ORDERS', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200}],
         'exchangeFilters': [], 'symbols':
         [{'symbol': 'BTCUSDT', 'status': 'TRADING', 'maintMarginPercent': '2.5000', 'requiredMarginPercent': '5.0000',
         'baseAsset': 'BTC', 'quoteAsset': 'USDT', 'pricePrecision': 2, 'quantityPrecision': 3, 'baseAssetPrecision': 8,
         'quotePrecision': 8,
         'filters': [{'minPrice': '0.01', 'maxPrice': '100000', 'filterType': 'PRICE_FILTER', 'tickSize': '0.01'},
         {'stepSize': '0.001', 'filterType': 'LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'stepSize': '0.001', 'filterType': 'MARKET_LOT_SIZE', 'maxQty': '1000', 'minQty': '0.001'},
         {'limit': 200, 'filterType': 'MAX_NUM_ORDERS'},
         {'multiplierDown': '0.8500', 'multiplierUp': '1.1500', 'multiplierDecimal': '4', 'filterType': 'PERCENT_PRICE'}],
         'orderTypes': ['LIMIT', 'MARKET', 'STOP'], 'timeInForce': ['GTC', 'IOC', 'FOK', 'GTX']}]}

        """

        path = '/api/v3/exchangeInfo'
        return self.request(req_method=RequestMethod.GET, path=path)

    def get_order_book(self, symbol, limit=5):
        """
        :param symbol: BTCUSDT, BNBUSDT ect, 交易对.
        :param limit: market depth.
        :return: return order_book in json 返回订单簿，json数据格式.
        """
        limits = [5, 10, 20, 50, 100, 500, 1000]
        if limit not in limits:
            limit = 5

        path = "/api/v3/depth"
        query_dict = {"symbol": symbol,
                      "limit": limit
                      }

        return self.request(RequestMethod.GET, path, query_dict)

    def get_kline(self, symbol, interval: Interval, start_time=None, end_time=None, limit=500, max_try_time=10):
        """
        获取K线数据.
        :param symbol:
        :param interval:
        :param start_time:
        :param end_time:
        :param limit:
        :param max_try_time:
        :return:
        """
        path = "/api/v3/klines"

        query_dict = {
            "symbol": symbol,
            "interval": interval.value,
            "limit": limit
        }

        if start_time:
            query_dict['startTime'] = start_time

        if end_time:
            query_dict['endTime'] = end_time

        for i in range(max_try_time):
            data = self.request(RequestMethod.GET, path, query_dict)
            if isinstance(data, list) and len(data):
                return data

    def get_latest_price(self, symbol):
        """
        :param symbol: 获取最新的价格.
        :return: {'symbol': 'BTCUSDT', 'price': '9168.90000000'}

        """
        path = "/api/v3/ticker/price"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_ticker(self, symbol):
        """
        :param symbol: 交易对
        :return: 返回的数据如下:
        {
        'symbol': 'BTCUSDT', 'bidPrice': '9168.50000000', 'bidQty': '1.27689900',
        'askPrice': '9168.51000000', 'askQty': '0.93307800'
        }
        """
        path = "/api/v3/ticker/bookTicker"
        query_dict = {"symbol": symbol}
        return self.request(RequestMethod.GET, path, query_dict)

    def get_all_tickers(self):
        """
        :param symbol: 交易对
        :return: 返回的数据如下:
        {
        'symbol': 'BTCUSDT', 'bidPrice': '9168.50000000', 'bidQty': '1.27689900',
        'askPrice': '9168.51000000', 'askQty': '0.93307800'
        }
        """
        path = "/api/v3/ticker/bookTicker"
        return self.request(RequestMethod.GET, path)

    def get_client_order_id(self):
        """
        generate the client_order_id for user.
        :return:
        """
        with self.order_count_lock:
            self.order_count += 1
            return "x-A6SIDXVS" + str(self.get_current_timestamp()) + str(self.order_count)

    def get_current_timestamp(self):
        """
        获取系统的时间.
        :return:
        """
        return int(time.time() * 1000)

    def _sign(self, params):
        """
        签名的方法， signature for the private request.
        :param params: request parameters
        :return:
        """

        query_string = self.build_parameters(params)
        hex_digest = hmac.new(self.secret.encode('utf8'), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        return query_string + '&signature=' + str(hex_digest)

    def place_order(self, symbol: str, order_side: OrderSide, order_type: OrderType, quantity: float, price: float,
                    client_order_id: str = None, time_inforce="GTC", stop_price=0):
        """

        :param symbol: 交易对名称
        :param order_side: 买或者卖， BUY or SELL
        :param order_type: 订单类型 LIMIT or other order type.
        :param quantity: 数量
        :param price: 价格.
        :param client_order_id: 用户的订单ID
        :param time_inforce:
        :param stop_price:
        :return:
        """

        path = '/api/v3/order'

        if client_order_id is None:
            client_order_id = self.get_client_order_id()

        params = {
            "symbol": symbol,
            "side": order_side.value,
            "type": order_type.value,
            "quantity": quantity,
            "price": price,
            "recvWindow": self.recv_window,
            "timestamp": self.get_current_timestamp(),
            "newClientOrderId": client_order_id
        }

        if order_type == OrderType.LIMIT:
            params['timeInForce'] = time_inforce

        if order_type == OrderType.MARKET:
            if params.get('price'):
                del params['price']

        if order_type == OrderType.STOP:
            if stop_price > 0:
                params["stopPrice"] = stop_price
            else:
                raise ValueError("stopPrice must greater than 0")

        return self.request(RequestMethod.POST, path=path, requery_dict=params, verify=True)

    def get_order(self, symbol: str, client_order_id: str):
        """
        获取订单状态.
        :param symbol:
        :param client_order_id:
        :return:
        """
        path = "/api/v3/order"
        prams = {"symbol": symbol, "timestamp": self.get_current_timestamp(), "origClientOrderId": client_order_id}

        return self.request(RequestMethod.GET, path, prams, verify=True)

    def cancel_order(self, symbol, client_order_id):
        """
        撤销订单.
        :param symbol:
        :param client_order_id:
        :return:
        """
        path = "/api/v3/order"
        params = {"symbol": symbol, "timestamp": self.get_current_timestamp(),
                  "origClientOrderId": client_order_id
                  }

        for i in range(0, 3):
            try:
                order = self.request(RequestMethod.DELETE, path, params, verify=True)
                return order
            except Exception as error:
                print(f'cancel order error:{error}')
        return

    def get_open_orders(self, symbol=None):
        """
        获取所有的订单.
        :param symbol: BNBUSDT, or BTCUSDT etc.
        :return:
        """
        path = "/api/v3/openOrders"

        params = {"timestamp": self.get_current_timestamp()}
        if symbol:
            params["symbol"] = symbol

        return self.request(RequestMethod.GET, path, params, verify=True)

    def cancel_open_orders(self, symbol):
        """
        撤销某个交易对的所有挂单
        :param symbol: symbol
        :return: return a list of orders.
        """
        path = "/api/v3/openOrders"

        params = {"timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window,
                  "symbol": symbol
                  }

        return self.request(RequestMethod.DELETE, path, params, verify=True)

    def get_account_info(self):
        """
        {'feeTier': 2, 'canTrade': True, 'canDeposit': True, 'canWithdraw': True, 'updateTime': 0, 'totalInitialMargin': '0.00000000',
        'totalMaintMargin': '0.00000000', 'totalWalletBalance': '530.21334791', 'totalUnrealizedProfit': '0.00000000',
        'totalMarginBalance': '530.21334791', 'totalPositionInitialMargin': '0.00000000', 'totalOpenOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000', 'assets':
        [{'asset': 'USDT', 'walletBalance': '530.21334791', 'unrealizedProfit': '0.00000000', 'marginBalance': '530.21334791',
        'maintMargin': '0.00000000', 'initialMargin': '0.00000000', 'positionInitialMargin': '0.00000000', 'openOrderInitialMargin': '0.00000000',
        'maxWithdrawAmount': '530.2133479100000'}]}
        :return:
        """
        path = "/api/v3/account"
        params = {"timestamp": self.get_current_timestamp(),
                  "recvWindow": self.recv_window
                  }
        return self.request(RequestMethod.GET, path, params, verify=True)
