from decimal import Decimal, ROUND_DOWN


class ContractHandler:
    def __init__(self, price_tick_str:str=None,price_tick:Decimal=None):
        # 假设 price_tick 是 Decimal 类型
        if price_tick_str is not None:
            self.price_tick = Decimal(price_tick_str)
        elif price_tick is not None:
            self.price_tick = price_tick

    def process_price(self, price):
        # 确保 price 也转换为 Decimal 类型
        price = Decimal(price)

        # 将 price 按照 price_tick 进行舍入
        processed_price = (price // self.price_tick) * self.price_tick

        # 返回处理后的价格（保留原始精度）
        return processed_price
