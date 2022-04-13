from typing import Union, Optional
from gridtrader.trader.engine import CtaEngine, EVENT_TIMER, EVENT_ACCOUNT
from gridtrader.trader.object import Status
from gridtrader.trader.utility import floor_to
from gridtrader.trader.object import OrderData, TickData, TradeData, ContractData, AccountData
from .template import CtaTemplate
from gridtrader.trader.utility import GridPositionCalculator, extract_vt_symbol


class SpotGridStrategy(CtaTemplate):
    """
    币安现货中性网格
    策略在震荡行情下表现很好，但是如果发生趋势行情，单次止损会比较大，导致亏损过多。

    免责声明: 本策略仅供测试参考，本人不负有任何责任。使用前请熟悉代码。测试其中的bugs, 请清楚里面的功能后再使用。
    币安邀请链接: https://www.binancezh.pro/cn/futures/ref/51bitquant
    合约邀请码：51bitquant


    Disclaimer:
    Invest in Crypto currency is high risk. Take care of yourself. I am not responsible for your investment.

    Binance Referral Link: https://www.binancezh.pro/cn/futures/ref/51bitquant

    """
    author = "51bitquant"

    # parameters
    upper_price = 0.0  # The grid strategy high/upper price 执行策略的最高价.
    bottom_price = 0.0  # The grid strategy low/bottom price 执行策略的最低价.
    grid_number = 100  # grid number 网格的数量.
    order_volume = 0.0  # order volume  每次下单的数量.
    invest_coin = "USDT"  # the coin you use to buy/trade.
    max_open_orders = 5  # max open price  一边订单的数量.

    # the strategy will stop when the price break the upper/bottom price, if you set the close_position when stop True,
    # it will automatically close your position.

    # variables
    avg_price = 0.0  # current average price for the position  持仓的均价
    step_price = 0.0  # price step between two grid 网格的间隔
    trade_times = 0  # trade times

    parameters = ["upper_price", "bottom_price", "grid_number", "order_volume", "invest_coin", "max_open_orders"]

    variables = ["avg_price", "step_price", "trade_times"]

    def __init__(self, cta_engine: CtaEngine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.long_orders_dict = {}  # long orders dict {'orderid': price}
        self.short_orders_dict = {}  # short orders dict {'orderid': price}

        self.tick: Union[TickData, None] = None
        self.contract_data: Optional[ContractData] = None

        self.pos_calculator = GridPositionCalculator()
        self.count_timer = 0
        self.cancel_order_timer = 0

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
        self.count_timer += 1
        if self.count_timer >= 10:
            self.count_timer = 0

            # remove the order(highest price order for short, lowest price to for long)
            # to keep the max open order meet requirements
            if len(self.long_orders_dict.keys()) > self.max_open_orders > 0:

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

            if len(self.short_orders_dict.keys()) > self.max_open_orders > 0:

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

        self.cancel_order_timer += 1
        if self.cancel_order_timer >= 120:
            self.cancel_order_timer = 0

            if not self.tick:
                return None

            trade_balance: Optional[AccountData] = self.get_trade_coin_balance()
            invest_balance: Optional[AccountData] = self.get_invest_coin_balance()

            if trade_balance and trade_balance.available < self.order_volume and len(
                    self.short_orders_dict.keys()) == 0 and len(self.long_orders_dict.keys()) > 0:
                # no short orders and no balance for sending sell order, we will cancel all order if the price move against the long order's price too far.
                # 没有卖单，只有买单的时候，检查买单的最新价格是不是偏离盘口价格太远，如果太远就撤单。
                vt = list(self.long_orders_dict.keys())[0]
                highest_price = self.long_orders_dict[vt]

                for orderid in self.long_orders_dict.keys():
                    order_price = self.long_orders_dict[orderid]
                    if highest_price <= order_price:
                        highest_price = order_price

                if float(self.tick.bid_price_1) - highest_price > 2 * float(self.step_price):
                    self.cancel_all()

            if invest_balance and invest_balance.available < float(self.tick.bid_price_1) * self.order_volume and len(
                    self.long_orders_dict.keys()) == 0 and len(self.short_orders_dict.keys()) > 0:
                # no long orders and no balance for sending buy order, we will cancel all order if the price move against the short order's price too far.
                # 买单位空，只有卖单的时候，也检查下卖单和盘口的价格是不是偏离太远了。
                vt = list(self.short_orders_dict.keys())[0]
                lowest_price = self.short_orders_dict[vt]

                for orderid in self.short_orders_dict.keys():
                    order_price = self.short_orders_dict[orderid]
                    if lowest_price >= order_price:
                        lowest_price = order_price

                if lowest_price - float(self.tick.bid_price_1) > 2 * float(self.step_price):
                    self.cancel_all()

        self.put_event()

    def get_invest_coin_balance(self) -> Optional[AccountData]:
        account_id = 'Spot.' + self.invest_coin.upper()
        return self.cta_engine.main_engine.get_account(account_id)

    def get_trade_coin_balance(self) -> Optional[AccountData]:
        symbol, exchange = extract_vt_symbol(self.vt_symbol)
        symbol = symbol.upper()
        if len(symbol) > len(self.invest_coin.upper()):
            trade_coin = symbol[0:len(symbol) - len(self.invest_coin.upper())]
            account_id = 'Spot.' + trade_coin
            return self.cta_engine.main_engine.get_account(account_id)
        else:
            return None

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

                    account: Optional[AccountData] = self.get_invest_coin_balance()
                    if account and account.available >= (price * self.order_volume) >= 10:
                        orders_ids = self.buy(price, self.order_volume)
                        for orderid in orders_ids:
                            self.long_orders_dict[orderid] = price

            if len(self.short_orders_dict.keys()) == 0:
                for i in range(self.max_open_orders):
                    price = self.bottom_price + (mid_count + i + 1) * self.step_price
                    if price > self.upper_price:
                        return

                    account: Optional[AccountData] = self.get_trade_coin_balance()
                    if account and account.available >= self.order_volume:
                        orders_ids = self.sell(price, self.order_volume)
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

                    orders_ids = self.sell(short_price, self.order_volume)

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
                        orders_ids = self.sell(short_price, self.order_volume)
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
