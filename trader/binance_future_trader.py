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


from gateway import BinanceFutureHttp, OrderStatus, OrderType, OrderSide
from utils import config
from utils import utility, round_to
from enum import Enum
import logging
from datetime import datetime

class BinanceFutureTrader(object):

    def __init__(self):
        """
        the binance future trader, 币安合约交易的网格交易,
        the grid trading in Future will endure a lot of risk， use it before you understand the risk and grid strategy.
        网格交易在合约上会有很大的风险，请注意风险
        """
        self.http_client = BinanceFutureHttp(api_key=config.api_key, secret=config.api_secret, proxy_host=config.proxy_host, proxy_port=config.proxy_port)

        self.buy_orders = []  # 买单. buy orders
        self.sell_orders = [] # 卖单. sell orders


    def get_bid_ask_price(self):

        ticker = self.http_client.get_ticker(config.symbol)

        bid_price = 0
        ask_price = 0
        if ticker:
            bid_price = float(ticker.get('bidPrice', 0))
            ask_price = float(ticker.get('askPrice', 0))

        return bid_price, ask_price

    def grid_trader(self):
        """
        执行核心逻辑，网格交易的逻辑.

        the grid trading logic
        :return:
        """

        bid_price, ask_price = self.get_bid_ask_price()
        print(f"bid_price: {bid_price}, ask_price: {ask_price}, time: {datetime.now()}")

        quantity = round_to(float(config.quantity), float(config.min_qty))

        self.buy_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高价到最低价.
        self.sell_orders.sort(key=lambda x: float(x['price']), reverse=True)  # 最高价到最低价.

        buy_delete_orders = []  # 需要删除买单
        sell_delete_orders = [] # 需要删除的卖单


        # 买单逻辑,检查成交的情况.
        for buy_order in self.buy_orders:

            check_order = self.http_client.get_order(buy_order.get('symbol', config.symbol),client_order_id=buy_order.get('clientOrderId'))

            if check_order:
                if check_order.get('status') == OrderStatus.CANCELED.value:
                    buy_delete_orders.append(buy_order)
                    print(f"buy order status was canceled: {check_order.get('status')}, time: {datetime.now()}")
                elif check_order.get('status') == OrderStatus.FILLED.value:
                    # 买单成交，挂卖单.
                    print(f"买单成交了, 时间: {datetime.now()}")
                    logging.info(f"买单成交时间: {datetime.now()}, 价格: {check_order.get('price')}, 数量: {check_order.get('origQty')}")

                    sell_price = round_to(float(check_order.get("price")) * (1 + float(config.gap_percent)), float(config.min_price))

                    if 0 < sell_price < ask_price:
                        # 防止价格
                        sell_price = round_to(ask_price, float(config.min_price))

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL, order_type=OrderType.LIMIT, quantity=quantity, price=sell_price)
                    if new_sell_order:
                        print(f"买单成交，下了对应价格的卖单: {new_sell_order}, 时间: {datetime.now()}")
                        buy_delete_orders.append(buy_order)
                        self.sell_orders.append(new_sell_order)

                    buy_price = round_to(float(check_order.get("price")) * (1 - float(config.gap_percent)),
                                     config.min_price)

                    if buy_price > bid_price > 0:
                        buy_price = round_to(buy_price, float(config.min_price))

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=quantity, price=buy_price)
                    if new_buy_order:
                        print(f"买单成交，下了更低价的买单: {new_buy_order}, 时间: {datetime.now()}")
                        self.buy_orders.append(new_buy_order)


                elif check_order.get('status') == OrderStatus.NEW.value:
                    print(f"buy order status is: New , 时间: {datetime.now()}")
                else:
                    print(f"buy order status is not above options: {check_order.get('status')}, 时间: {datetime.now()}")

        # 过期或者拒绝的订单删除掉.
        for delete_order in buy_delete_orders:
            self.buy_orders.remove(delete_order)

        # 卖单逻辑, 检查卖单成交情况.
        for sell_order in self.sell_orders:

            check_order = self.http_client.get_order(sell_order.get('symbol', config.symbol),
                                               client_order_id=sell_order.get('clientOrderId'))
            if check_order:
                if check_order.get('status') == OrderStatus.CANCELED.value:
                    sell_delete_orders.append(sell_order)

                    print(f"sell order status was canceled: {check_order.get('status')}, 时间: {datetime.now()}")
                elif check_order.get('status') == OrderStatus.FILLED.value:
                    print(f"卖单成交了, 时间: {datetime.now()}")
                    logging.info(
                        f"卖单成交时间: {datetime.now()}, 价格: {check_order.get('price')}, 数量: {check_order.get('origQty')}")
                    # 卖单成交，先下买单.
                    buy_price = round_to(float(check_order.get("price")) * (1 - float(config.gap_percent)), float(config.min_price))
                    if buy_price > bid_price > 0:
                        buy_price = round_to(buy_price, float(config.min_price))

                    new_buy_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.BUY,
                                                             order_type=OrderType.LIMIT, quantity=quantity, price=buy_price)
                    if new_buy_order:
                        print(f"卖单成交，下了对应价格的买单: {new_buy_order}, 时间: {datetime.now()}")
                        sell_delete_orders.append(sell_order)
                        self.buy_orders.append(new_buy_order)

                    sell_price = round_to(float(check_order.get("price")) * (1 + float(config.gap_percent)), float(config.min_price))

                    if 0 < sell_price < ask_price:
                        # 防止价格
                        sell_price = round_to(ask_price, float(config.min_price))

                    new_sell_order = self.http_client.place_order(symbol=config.symbol, order_side=OrderSide.SELL,
                                                                 order_type=OrderType.LIMIT, quantity=quantity,
                                                                 price=sell_price)
                    if new_sell_order:
                        print(f"卖单成交，下了更高价的卖单: {new_sell_order}, 时间: {datetime.now()}")
                        self.sell_orders.append(new_sell_order)

                elif check_order.get('status') == OrderStatus.NEW.value:
                    print(f"sell order status is: New, 时间: {datetime.now()}")
                else:
                    print(f"sell order status is not in above options: {check_order.get('status')}, 时间: {datetime.now()}")

        # 过期或者拒绝的订单删除掉.
        for delete_order in sell_delete_orders:
            self.sell_orders.remove(delete_order)

        # 没有买单的时候.
        if len(self.buy_orders) <= 0:
            if bid_price > 0:
                price = round_to(bid_price * (1 - float(config.gap_percent)), float(config.min_price))

                buy_order = self.http_client.place_order(symbol=config.symbol,order_side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=quantity,price=price)
                print(f'没有买单，根据盘口下买单: {buy_order}, 时间: {datetime.now()}')
                if buy_order:
                    self.buy_orders.append(buy_order)
        else:
            self.buy_orders.sort(key=lambda x: float(x['price']), reverse=False) # 最低价到最高价
            delete_orders = []
            for i in range(len(self.buy_orders) -1):
                order = self.buy_orders[i]
                next_order = self.buy_orders[i+1]

                if float(next_order['price'])/float(order['price']) - 1 < 0.001:
                    print(f"买单之间价差太小，撤销订单：{next_order}, 时间: {datetime.now()}")
                    cancel_order = self.http_client.cancel_order(next_order.get('symbol'),
                                                          client_order_id=next_order.get('clientOrderId'))
                    if cancel_order:
                        delete_orders.append(next_order)

            for order in delete_orders:
                self.buy_orders.remove(order)


            if len(self.buy_orders) > int(config.max_orders): # 最多允许的挂单数量.
                # 订单数量比较多的时候.
                self.buy_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低价到最高价

                delete_order = self.buy_orders[0]
                print(f"订单太多了，撤销最低价的买单：{delete_order}, 时间: {datetime.now()}")
                order = self.http_client.cancel_order(delete_order.get('symbol'), client_order_id=delete_order.get('clientOrderId'))
                if order:
                    self.buy_orders.remove(delete_order)

        # 没有卖单的时候.
        if len(self.sell_orders) <= 0:
            if ask_price > 0:
                price = round_to(ask_price * (1 + float(config.gap_percent)), float(config.min_price))
                sell_order = self.http_client.place_order(symbol=config.symbol,order_side=OrderSide.SELL, order_type=OrderType.LIMIT, quantity=quantity,price=price)
                print(f'没有卖单，根据盘口下卖单:{sell_order} , 时间: {datetime.now()}')
                if sell_order:
                    self.sell_orders.append(sell_order)

        else:
            self.sell_orders.sort(key=lambda x: float(x['price']), reverse=False)  # 最低价到最高价
            delete_orders = []
            for i in range(len(self.sell_orders) - 1):
                order = self.sell_orders[i]
                next_order = self.sell_orders[i + 1]

                if float(next_order['price']) / float(order['price']) - 1 < 0.001:
                    print(f"卖单之间价差太小，撤销订单:{next_order}, 时间: {datetime.now()}")
                    cancel_order = self.http_client.cancel_order(next_order.get('symbol'),
                                                                 client_order_id=next_order.get('clientOrderId'))
                    if cancel_order:
                        delete_orders.append(next_order)

            for order in delete_orders:
                self.sell_orders.remove(order)

            if len(self.sell_orders) > int(config.max_orders): # 最多允许的挂单数量.
                # 订单数量比较多的时候.
                self.sell_orders.sort(key=lambda x: x['price'], reverse=True)  # 最高价到最低价

                delete_order = self.sell_orders[0]
                print(f"订单太多了，撤销最高价的卖单：{delete_order}, 时间:{datetime.now()}")
                order = self.http_client.cancel_order(delete_order.get('symbol'),
                                                      client_order_id=delete_order.get('clientOrderId'))
                if order:
                    self.sell_orders.remove(delete_order)



