from decimal import Decimal, ROUND_DOWN
from typing import Union, Optional

import ccxt

from gridtrader.trader.object import OrderData, TickData, TradeData, ContractData
from gridtrader.trader.object import Status
from gridtrader.trader.utility import GridPositionCalculator
from gridtrader.tools.common.contract_handler import ContractHandler
from .template import CtaTemplate
from ..engine import CtaEngine
from ...event import EVENT_TIMER


class FutureGridStrategy(CtaTemplate):
    """
    优化后的币安合约网格策略，支持多头和空头模式。
    多头模式下，下方网格的单格金额是上方网格的1.1倍。
    空头模式下，上方网格的单格金额是下方网格的1.1倍。
    总金额保持不变，且满足最小下单数量。
    """
    author = "51bitquant"

    # 参数
    upper_price = 0.0  # 策略最高价
    bottom_price = 0.0  # 策略最低价
    grid_number = 100  # 网格数量
    max_open_orders = 5  # 最大同时挂单数
    order_amount = 5000  # 下单总金额
    start_price = 0.0  # 启动价格
    stop_loss_price = 0.0  # 止损价格
    direction_int = 1  # 方向：1为多头，-1为空头

    # 变量
    avg_price = 0.0  # 持仓均价
    step_price = 0.0  # 网格间距
    trade_times = 0  # 成交次数
    price_volume_dict = {}  # 保存每个价格对应的下单数量
    start_price_triggered = False  # 启动价格是否已触发
    lower_grid_total_volume = 0.0  # 下方网格的总下单量
    upper_grid_total_volume = 0.0  # 上方网格的总下单量
    first_order = True  # 标记是否是第一次下单
    orders_dict = {}  # 存储所有订单的字典

    parameters = ["bottom_price", "upper_price",  "max_open_orders", "order_amount", "start_price", "direction_int","stop_loss_price"]
    variables = ["avg_price", "step_price", "trade_times", "price_volume_dict", "start_price_triggered",
                 "lower_grid_total_volume", "upper_grid_total_volume"]

    def __init__(self, cta_engine: CtaEngine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.is_sell_outed = False
        self.exchange = self.create_exchange()  # 创建 ccxt 交易所实例
        self.long_orders_dict = {}  # 多单挂单字典
        self.short_orders_dict = {}  # 空单挂单字典
        self.tick: Union[TickData, None] = None
        self.contract_data: Optional[ContractData] = None
        self.pos_calculator = GridPositionCalculator()
        self.timer_count = 0
        self._ContractHandler = None
        self.fake_active_orders_price_list = None

    def create_exchange(self):
        """创建 ccxt 交易所实例"""
        # 获取历史订单
        fbinance = ccxt.binance()
        binance_key4 = 'qBFimviRucbMNt9bcPKWBIrhrAqJpcGlPjDMkiIFj04GzhT0YNsLq9A1XU9IFC2Y'
        binance_secret4 = 'UvkbgNauNOGMwYxnGbz81hFYbhGaEdNdFfirwLUIE72McPhc4eJOkSelS65Stbpu'
        fbinance.apiKey = binance_key4
        fbinance.secret = binance_secret4
        fbinance.enableRateLimit = True
        fbinance.password = '5601564a'
        fbinance.options['defaultType'] = 'future'
        fbinance.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
        fbinance.name = 'future-binance'
        fbinance.enableRateLimit = True

        exchange = fbinance

        return exchange

    def calculate_grid_parameters(self):
        """
        根据下单金额或手动设置的价格范围和网格数量计算网格参数。
        确保每个网格的单格数量满足最小下单数量，同时保持总下单金额不变。
        """
        if not self.order_amount:
            return

        ###
        fake_active_orders = self.cta_engine.main_engine.future_gateway.active_orders
        self.fake_active_orders_price_list = [float(order.price) for order in fake_active_orders.values()]

        self._ContractHandler = ContractHandler(self.contract_data.price_tick)

        # 获取最小下单数量
        min_volume = self.contract_data.min_volume

        # 根据 min_volume 确定需要保留的小数位数
        decimal_places = abs(Decimal(str(min_volume)).as_tuple().exponent)
        quantize_str = f"0.{'0' * decimal_places}"  # 例如 min_volume=0.001 -> "0.000"

        # 计算价格范围
        price_range = self.upper_price - self.bottom_price
        if price_range <= 0:
            raise ValueError("价格区间设置错误，上限价格必须大于下限价格。")

        if self.vt_symbol.split(".")[0] == "BTCUSDT":
            rate = 0.003
        else:
            rate = 0.005

        # 初始网格数量
        grid_spacing = self.upper_price * rate  # 网格间距为下限价格的 0.6%
        self.grid_number = max(1, int(price_range / grid_spacing))  # 初始网格数量

        # 调整网格数量，确保每个网格的币数量满足最小下单数量
        while True:
            # 计算网格间距
            self.step_price = self._ContractHandler.process_price(price_range / self.grid_number)

            # 计算下方网格和上方网格的数量
            lower_grid_number = self.grid_number // 2
            upper_grid_number = self.grid_number - lower_grid_number

            # 计算下方网格和上方网格的单格金额
            if self.direction_int == 1:  # 多头模式
                upper_grid_amount = self.order_amount / (upper_grid_number * 1.1 + lower_grid_number)
                lower_grid_amount = upper_grid_amount * 1.1
            else:  # 空头模式
                lower_grid_amount = self.order_amount / (lower_grid_number * 1.1 + upper_grid_number)
                upper_grid_amount = lower_grid_amount * 1.1

            # 计算每个网格的币数量
            self.price_volume_dict = {}
            total_amount = 0
            self.lower_grid_total_volume = 0.0  # 重置下方网格的总下单量
            self.upper_grid_total_volume = 0.0  # 重置上方网格的总下单量
            for i in range(self.grid_number):
                price = self.bottom_price + i * self.step_price
                if i < lower_grid_number:
                    volume = lower_grid_amount / price  # 金额转换为币数量
                    self.lower_grid_total_volume += volume  # 累加下方网格的总下单量
                else:
                    volume = upper_grid_amount / price  # 金额转换为币数量
                    self.upper_grid_total_volume += volume  # 累加上方网格的总下单量

                # 根据 min_volume 保留小数位数
                volume = float(Decimal(volume).quantize(Decimal(quantize_str), rounding=ROUND_DOWN))

                # 如果币数量小于最小下单数量，减少网格数量并重新计算
                if volume < min_volume:
                    self.grid_number -= 1
                    if self.grid_number < 1:
                        raise ValueError("无法满足最小下单数量要求，请调整参数。")
                    break
                else:
                    price_dc = self._ContractHandler.process_price(price)
                    # 将 Decimal 键转换为 float
                    price_float = float(price_dc)
                    self.price_volume_dict[price_float] = volume
                    total_amount += volume * price
            else:
                # 所有网格的币数量都满足最小下单数量要求，退出循环
                break

        # 检查总金额是否超过设定值
        if total_amount > self.order_amount:
            scale_factor = self.order_amount / total_amount
            for price in self.price_volume_dict:
                self.price_volume_dict[price] = float(
                    Decimal(self.price_volume_dict[price] * scale_factor).quantize(Decimal(quantize_str),
                                                                                   rounding=ROUND_DOWN))
            # 按比例调整下方和上方网格的总下单量
            self.lower_grid_total_volume *= scale_factor
            self.upper_grid_total_volume *= scale_factor

        self.write_log(
            f"Calculated Parameters: Upper Price: {self.upper_price}, Bottom Price: {self.bottom_price}, "
            f"Grid Number: {self.grid_number}, Step Price: {self.step_price}, "
            f"Price Volume Dict: {self.price_volume_dict}, "
            f"Lower Grid Total Volume: {self.lower_grid_total_volume}, "
            f"Upper Grid Total Volume: {self.upper_grid_total_volume}, "
            f"Mode: {'Long' if self.direction_int == 1 else 'Short'}")

        # 计算价格变化率
        self.calculate_price_change_rate()
    # def get_min_volume(self, vt_symbol):
    #     """获取最小下单数量"""
    #     symbol = vt_symbol.split(".")[0]
    #     data = settings_exchange.load_markets()
    #     symbol = symbol.replace("USDT", "/USDT")
    #     precision = data[symbol]["precision"]["amount"]
    #     return 10 ** -precision  # 最小下单数量

    def on_init(self):
        """策略初始化回调"""
        self.write_log("Init Strategy")

    def on_start(self):
        self.contract_data = self.cta_engine.main_engine.get_contract(self.vt_symbol)
        """策略启动回调"""
        self.calculate_grid_parameters()
        # self.avoid_finished_orders()
        self.write_log(f"Calculated Parameters: Upper Price: {self.upper_price}, Bottom Price: {self.bottom_price}, "
                       f"Grid Number: {self.grid_number}, Step Price: {self.step_price}, "
                       f"Price Volume Dict: {self.price_volume_dict}")

        if not self.contract_data:
            self.write_log(f"Could Not Find The Symbol:{self.vt_symbol}, Please Connect the Api First.")
            self.inited = False
        else:
            self.inited = True

        self.pos_calculator.pos = self.pos
        self.pos_calculator.avg_price = self.avg_price

        self.cta_engine.event_engine.register(EVENT_TIMER, self.process_timer)

    def on_stop(self):
        """策略停止回调"""
        self.write_log("Stop Strategy")
        self.cta_engine.event_engine.unregister(EVENT_TIMER, self.process_timer)

    def process_timer(self, event):
        """定时器回调"""
        self.timer_count += 1
        if self.timer_count >= 10:
            self.timer_count = 0

            # 移除超出最大挂单数的订单
            if len(self.long_orders_dict.keys()) > self.max_open_orders:
                cancel_order_id = min(self.long_orders_dict.keys(), key=lambda k: self.long_orders_dict[k])
                self.cancel_order(cancel_order_id)

            if len(self.short_orders_dict.keys()) > self.max_open_orders:
                cancel_order_id = max(self.short_orders_dict.keys(), key=lambda k: self.short_orders_dict[k])
                self.cancel_order(cancel_order_id)

            self.put_event()

    def on_tick(self, tick: TickData):
        """Tick 数据回调"""
        if tick and tick.bid_price_1 > 0 and self.contract_data:
            self.tick = tick

            # 检查是否达到止损价格
            if self.stop_loss_price > 0 and tick.bid_price_1 <= self.stop_loss_price and not self.is_sell_outed:
                self.write_log(f"触发止损，当前价格: {tick.bid_price_1}，止损价格: {self.stop_loss_price}")
                self.on_stop()  # 触发停止功能
                self.sell_market()  # 执行市价卖出
                return

            if self.upper_price - self.bottom_price <= 0:
                return

            # 获取当前价格
            current_price = float(self.tick.bid_price_1)

            # 检查是否达到启动价格并执行相应操作
            self.check_start_price_and_execute(current_price)

            # 如果启动价格未触发，则不执行网格交易
            if not self.start_price_triggered:
                return

            # 从 price_volume_dict 中取出当前价格上下方的网格价格
            sorted_prices = sorted(self.price_volume_dict.keys())
            lower_prices = [price for price in sorted_prices if price < current_price]
            upper_prices = [price for price in sorted_prices if price > current_price]

            # 处理多头挂单（下方网格）
            if len(self.long_orders_dict.keys()) == 0:
                for price in lower_prices[-self.max_open_orders:]:  # 取最接近当前价格的 max_open_orders 个
                    volume = self.price_volume_dict.get(price)
                    if volume is None:
                        continue  # 如果价格不在字典中，跳过

                    # 下单
                    orders_ids = self.buy(price, volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = price

            # 处理空头挂单（上方网格）
            if len(self.short_orders_dict.keys()) == 0:
                for price in upper_prices[:self.max_open_orders]:  # 取最接近当前价格的 max_open_orders 个
                    volume = self.price_volume_dict.get(price)
                    if volume is None:
                        continue  # 如果价格不在字典中，跳过

                    # 下单
                    orders_ids = self.short(price, volume)
                    for orderid in orders_ids:
                        self.short_orders_dict[orderid] = price

            # 第一次下单后，将标志设置为 False
            if self.first_order:
                self.first_order = False

    def on_order(self, order: OrderData):
        """订单状态回调"""
        if order.vt_orderid not in (list(self.short_orders_dict.keys()) + list(self.long_orders_dict.keys())):
            return

        self.pos_calculator.update_position(order)
        self.avg_price = self.pos_calculator.avg_price
        _ContractHandler = ContractHandler(self.contract_data.price_tick)

        if order.status == Status.ALLTRADED:
            short_price = float(order.price) + float(self.step_price)
            long_price = float(order.price) - float(self.step_price)

            if not(long_price >= self.bottom_price and short_price <= self.upper_price):
                return

            if order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]
                self.trade_times += 1

                # 使用 min() 找最接近的价格
                short_price, volume = self.getVolume(short_price)
                if short_price <= self.upper_price:
                    if short_price in self.short_orders_dict.values():  # 检查是否已有该价格的订单
                        self.write_log(f" short_price 跳过 {short_price}。")
                        return

                    orders_ids = self.short(short_price, volume)
                    for orderid in orders_ids:
                        self.short_orders_dict[orderid] = short_price  # 存储在总字典中

                ## 补充买单
                if len(self.long_orders_dict.keys()) < self.max_open_orders:
                    count = len(self.long_orders_dict.keys()) + 1
                    long_price = float(order.price) - float(self.step_price) * count
                    if long_price >= self.bottom_price:
                        ## 方式3：使用 min() 找最接近的价格
                        closest_price, volume = self.getVolume(long_price)

                        if closest_price in self.long_orders_dict.values():  # 检查是否已有该价格的订单
                            self.write_log(f" long_price 跳过 {closest_price}。")
                            return

                        orders_ids = self.buy(closest_price, volume)
                        for orderid in orders_ids:
                            self.long_orders_dict[orderid] = long_price

            if order.vt_orderid in self.short_orders_dict.keys():
                del self.short_orders_dict[order.vt_orderid]  # 从总字典中删除已成交的订单
                self.trade_times += 1

                # 使用 min() 找最接近的价格
                long_price, volume = self.getVolume(long_price)
                if long_price >= self.bottom_price:
                    if long_price in self.long_orders_dict.values():  # 检查是否已有该价格的订单
                        self.write_log(f" long_price 跳过 {long_price}。")
                        return

                    orders_ids = self.buy(long_price, volume)
                    for orderid in orders_ids:
                        self.long_orders_dict[orderid] = long_price  # 存储在总字典中

                ## 补充卖单
                if len(self.short_orders_dict.keys()) < self.max_open_orders:
                    count = len(self.short_orders_dict.keys()) + 1
                    short_price = float(order.price) + float(self.step_price) * count
                    if short_price <= self.upper_price:
                        ## 方式3：使用 min() 找最接近的价格
                        closest_price, volume = self.getVolume(short_price)

                        if closest_price in self.short_orders_dict.values():  # 检查是否已有该价格的订单
                            self.write_log(f" short_price 跳过 {closest_price}。")
                            return

                        orders_ids = self.short(closest_price, volume)
                        for orderid in orders_ids:
                            self.short_orders_dict[orderid] = short_price

        if not order.is_active():
            if order.vt_orderid in self.long_orders_dict.keys():
                del self.long_orders_dict[order.vt_orderid]
            elif order.vt_orderid in self.short_orders_dict.keys():
                del self.short_orders_dict[order.vt_orderid]

        self.put_event()

    def on_trade(self, trade: TradeData):
        """成交回调"""
        self.put_event()

    def check_start_price_and_execute(self, current_price: float):
        if self.start_price == 0:
            self.start_price_triggered = True  # 标记启动价格已触发

        # if self.position != 0:
        #     self.start_price_triggered = True  # 存在的话，就是启动了

        """
        检查当前价格是否达到启动价格，如果是，则立即执行相应的操作。
        """
        if self.direction_int == 1:  # 多头模式
            if current_price <= self.start_price and not self.start_price_triggered:
                # 获取所有空头订单的价格和数量
                for price, volume in self.price_volume_dict.items():
                    if price > current_price:  # 空头订单的价格高于当前价格
                        # 立即买入
                        orders_ids = self.buy(price, volume)
                        for orderid in orders_ids:
                            self.long_orders_dict[orderid] = price
                self.start_price_triggered = True  # 标记启动价格已触发
        elif self.direction_int == -1:  # 空头模式
            if current_price >= self.start_price and not self.start_price_triggered:
                # 获取所有多头订单的价格和数量
                for price, volume in self.price_volume_dict.items():
                    if price < current_price:  # 多头订单的价格低于当前价格
                        # 立即卖出
                        orders_ids = self.sell(price, volume)
                        for orderid in orders_ids:
                            self.short_orders_dict[orderid] = price
                self.start_price_triggered = True  # 标记启动价格已触发

    def calculate_price_change_rate(self):
        """
        计算 price_volume_dict 中各个价格之间的变化率。
        返回一个字典，键为价格对 (prev_price, current_price)，值为变化率。
        """
        if not self.price_volume_dict:
            return {}

        # 将价格排序
        sorted_prices = sorted(self.price_volume_dict.keys())

        # 计算变化率
        change_rate_dict = {}
        for i in range(1, len(sorted_prices)):
            prev_price = sorted_prices[i - 1]
            current_price = sorted_prices[i]
            change_rate = (current_price - prev_price) / prev_price * 100  # 变化率（百分比）
            change_rate_dict[(prev_price, current_price)] = change_rate
            print(current_price,change_rate)

        return change_rate_dict

    def avoid_finished_orders(self):
        symbol = self.vt_symbol.split(".")[0]
        symbol = symbol.replace("USDT", "/USDT")
        orders = self.exchange.fetch_my_trades(symbol=symbol, limit=10)

        self.set_avoid_finished_orders = set()
        # 打印订单信息
        for i, order in enumerate(orders):
            print(f"订单 {i + 1}:")
            print(f"  时间: {self.exchange.iso8601(order['timestamp'])}")
            print(f"  交易对: {order['symbol']}")
            print(f"  类型: {order['side']}")  # 买入(buy)或卖出(sell)
            print(f"  数量: {order['amount']}")
            print(f"  成交价格: {order['price']}")
            print(f"  成交金额: {order['cost']}")
            print(f"  手续费: {order['fee']['cost']} {order['fee']['currency']}")
            print("-" * 30)

            self.set_avoid_finished_orders.add(order['price'])

    ## 使用 min() 找最接近的价格
    def getVolume(self, price):
        closest_price = min(self.price_volume_dict.keys(), key=lambda x: abs(x - price))
        volume = self.price_volume_dict.get(closest_price, None)

        return closest_price, volume

    def sell_market(self):
        """市价卖出功能"""
        symbol2 = self.vt_symbol.split(".")[0]  # 获取交易对
        symbol = symbol2.replace("USDT", "/USDT")

        # 获取合约账户余额信息
        balance = self.exchange.fetch_balance({"type": "future"})
        btc_positions = balance.get('info', {}).get('positions', [])

        # 过滤出目标交易对的持仓
        btc_position = next((pos for pos in btc_positions if pos["symbol"] == symbol2), None)

        if not btc_position:
            self.write_log(f"未持有 {symbol} 的仓位，无法执行市价卖出。")
            return

        position_amt = float(btc_position.get("positionAmt", 0))  # 获取仓位数量

        if position_amt == 0:
            self.write_log(f"{symbol} 持仓数量为 0，无法执行市价卖出。")
            return

        self.write_log(f"持有 {position_amt} 个 {symbol}，准备市价卖出。")

        # 使用 ccxt 执行市价卖出
        self.exchange.create_market_sell_order(symbol, abs(position_amt))
        self.write_log(f"已市价卖出 {btc_position} 个 {symbol}。")
        self.is_sell_outed = True