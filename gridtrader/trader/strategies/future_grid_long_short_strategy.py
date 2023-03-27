from ..engine import CtaEngine, EVENT_TIMER

from gridtrader.trader.object import Status
from typing import Union, Optional
from gridtrader.trader.utility import floor_to
from gridtrader.trader.object import OrderData, TickData, TradeData, ContractData
from .template import CtaTemplate
from gridtrader.trader.utility import GridPositionCalculator


class FutureGridLongShortStrategy(CtaTemplate):
    """
    Long Short Grid Strategy: you may init the grid strategy with Long/Short Position
    Binance Referral Link: https://www.binance.com/cn/futures/ref/51bitquant
    Invitee code: 51bitquant

    Disclaimer:
    Invest in Crypto currency is high risk. Take care of yourself. I am not responsible for your investment.
    Binance Referral Link: https://www.binance.com/cn/futures/ref/51bitquant

    """
    author = "51bitquant"

    # parameters
    initial_volume = 0.0  # if greater than zero, means LONG, if less than zero: means SHORT.
    upper_price = 0.0  # The grid strategy high/upper price 执行策略的最高价.
    bottom_price = 0.0  # The grid strategy low/bottom price 执行策略的最低价.
    grid_number = 100  # grid number 网格的数量.
    order_volume = 0.05  # order volume  每次下单的数量.
    max_open_orders = 5  # max open price  一边订单的数量.

    # the strategy will stop when the price break the upper/bottom price, if you set the close_position when stop True,
    # it will automatically close your position.

    # variables
    avg_price = 0.0  # current average price for the position  持仓的均价
    step_price = 0.0  # price step between two grid 网格的间隔
    trade_times = 0  # trade times

    parameters = ["initial_volume", "upper_price", "bottom_price", "grid_number", "order_volume", "max_open_orders"]

    variables = ["avg_price", "step_price", "trade_times"]

    def __init__(self, cta_engine: CtaEngine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.long_orders_dict = {}  # long orders dict {'orderid': price}
        self.short_orders_dict = {}  # short orders dict {'orderid': price}

        self.tick: Union[TickData, None] = None
        self.contract_data: Optional[ContractData] = None

        self.pos_calculator = GridPositionCalculator()
        self.timer_count = 0

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("Init Strategy")

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("Start Strategy")
        self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)

        if not self.contract_data:
            self.write_log(f"Could Not Find The Symbol:{self.vt_symbol}, Please Connect the Api First.")
            self.inited = False
        else:
            self.inited = True

        self.pos_calculator.pos = self.pos
        self.pos_calculator.avg_price = self.avg_price

        self.cta_engine.event_engine.register(EVENT_TIMER, self.process_timer)

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("Stop Strategy")
        self.cta_engine.event_engine.unregister(EVENT_TIMER, self.process_timer)

    def process_timer(self, event):
        self.timer_count += 1
        if self.timer_count >= 10:
            self.timer_count = 0

            # remove the order(highest price order for short, lowest price to for long)
            # to keep the max open order meet requirements
            if len(self.long_orders_dict.keys()) > self.max_open_orders:

                vt = list(self.long_orders_dict.keys())[0]
                lowest_price = self.long_orders_dict[vt]
                cancel_order_id = None

                for orderid in self.long_orders_dict.keys():
                    order_price = self.long_orders_dict[orderid]
                    if lowest_price >= order_price:
                        cancel_order_id = orderid
                        lowest_price = order_price

                if cancel_order_id:
                    self.cancel_order(cancel_order_id)

            if len(self.short_orders_dict.keys()) > self.max_open_orders:

                vt = list(self.short_orders_dict.keys())[0]
                highest_price = self.short_orders_dict[vt]
                cancel_order_id = None

                for orderid in self.short_orders_dict.keys():
                    order_price = self.short_orders_dict[orderid]
                    if highest_price <= order_price:
                        cancel_order_id = orderid
                        highest_price = order_price

                if cancel_order_id:
                    self.cancel_order(cancel_order_id)

            self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """

        if tick and tick.bid_price_1 > 0 and self.contract_data:
            self.tick = tick

            if self.upper_price - self.bottom_price <= 0:
                return

            step_price = (self.upper_price - self.bottom_price) / self.grid_number

            self.step_price = float(floor_to(step_price, self.contract_data.price_tick))

            mid_count = round((float(self.tick.bid_price_1) - self.bottom_price) / self.step_price)

            if len(self.long_orders_dict.keys()) == 0:

                for i in range(self.max_open_orders):
                    price = self.bottom_price + (mid_count - i - 1) * self.step_price
                    if price < self.bottom_price:
                        return

                    orders_ids = self.buy(price, self.order_volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = price

            if len(self.short_orders_dict.keys()) == 0:
                for i in range(self.max_open_orders):
                    price = self.bottom_price + (mid_count + i + 1) * self.step_price
                    if price > self.upper_price:
                        return

                    orders_ids = self.short(price, self.order_volume)

                    for orderid in orders_ids:
                        self.short_orders_dict[orderid] = price

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        if order.vt_orderid not in (list(self.short_orders_dict.keys()) + list(self.long_orders_dict.keys())):
            return

        self.pos_calculator.update_position(order)
        self.avg_price = self.pos_calculator.avg_price

        if order.status == Status.ALLTRADED:

            if order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]

                self.trade_times += 1

                short_price = float(order.price) + float(self.step_price)

                if short_price <= self.upper_price:
                    orders_ids = self.short(short_price, self.order_volume)

                    for orderid in orders_ids:
                        self.short_orders_dict[orderid] = short_price

                if len(self.long_orders_dict.keys()) < self.max_open_orders:
                    long_price = float(order.price) - float(self.step_price) * self.max_open_orders
                    if long_price >= self.bottom_price:
                        orders_ids = self.buy(long_price, self.order_volume)
                        for orderid in orders_ids:
                            self.long_orders_dict[orderid] = long_price

            if order.vt_orderid in self.short_orders_dict.keys():
                del self.short_orders_dict[order.vt_orderid]

                self.trade_times += 1
                long_price = float(order.price) - float(self.step_price)
                if long_price >= self.bottom_price:
                    orders_ids = self.buy(long_price, self.order_volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = long_price

                if len(self.short_orders_dict.keys()) < self.max_open_orders:
                    short_price = float(order.price) + float(self.step_price) * self.max_open_orders

                    if short_price <= self.upper_price:
                        orders_ids = self.short(short_price, self.order_volume)
                        for orderid in orders_ids:
                            self.short_orders_dict[orderid] = short_price

        if not order.is_active():
            if order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]

            elif order.vt_orderid in self.short_orders_dict.keys():

                del self.short_orders_dict[order.vt_orderid]

        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()
