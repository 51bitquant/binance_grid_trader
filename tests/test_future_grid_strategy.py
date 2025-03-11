import unittest
from unittest.mock import Mock, patch
from decimal import Decimal

from gridtrader.trader.constant import Product, Exchange
from gridtrader.trader.strategies.future_grid_strategy import FutureGridStrategy
from gridtrader.trader.object import TickData, OrderData, ContractData, Status
from gridtrader.trader.utility import GridPositionCalculator

class TestFutureGridStrategy(unittest.TestCase):
    def setUp(self):
        """测试前的设置"""
        self.cta_engine = Mock()
        self.cta_engine.main_engine = Mock()
        
        # 模拟合约数据
        self.contract = ContractData(
            symbol="BTC-USDT",
            exchange=Exchange.BINANCE,
            name="BTC永续合约",
            price_tick=0.01,
            product=Product.FUTURES,
            gateway_name="BTCUSDT",
            min_volume=0.001
        )
        self.cta_engine.main_engine.get_contract = Mock(return_value=self.contract)
        
        # 创建策略实例
        self.strategy = FutureGridStrategy(
            cta_engine=self.cta_engine,
            strategy_name="test_strategy",
            vt_symbol="BTC-USDT.BINANCE",
            setting={
                "upper_price": 50000.0,
                "bottom_price": 40000.0,
                "grid_number": 100,
                "max_open_orders": 5,
                "order_amount": 5000.0,
                "start_price": 45000.0,
                "direction_int": 1
            }
        )
        
        # 模拟gateway
        self.fake_gateway = Mock()
        self.fake_gateway.active_orders = {}
        self.cta_engine.main_engine.future_gateway = self.fake_gateway
        self.contract_data = self.cta_engine.main_engine.get_contract(self.strategy.vt_symbol)

    def test_calculate_grid_parameters(self):
        """测试网格参数计算"""
        self.strategy.calculate_grid_parameters()
        
        # 验证基本参数是否正确计算
        self.assertGreater(len(self.strategy.price_volume_dict), 0)
        self.assertGreater(self.strategy.step_price, 0)
        
        # 验证网格价格范围
        prices = list(self.strategy.price_volume_dict.keys())
        self.assertGreaterEqual(min(prices), self.strategy.bottom_price)
        self.assertLessEqual(max(prices), self.strategy.upper_price)
        
        # 验证下单量是否满足最小要求
        for volume in self.strategy.price_volume_dict.values():
            self.assertGreaterEqual(volume, self.contract.min_volume)

    def test_check_start_price_and_execute(self):
        """测试启动价格检查和执行"""
        self.strategy.calculate_grid_parameters()
        
        # 测试多头模式
        self.strategy.direction_int = 1
        self.strategy.start_price_triggered = False
        
        # 模拟买入订单
        self.strategy.buy = Mock(return_value=["test_order_id"])
        
        # 测试价格低于启动价格
        self.strategy.check_start_price_and_execute(44000.0)
        self.assertTrue(self.strategy.start_price_triggered)
        self.strategy.buy.assert_called()

    def test_on_tick(self):
        """测试Tick数据处理"""
        self.strategy.calculate_grid_parameters()
        self.strategy.start_price_triggered = True
        
        # 创建模拟Tick数据
        tick = TickData(
            symbol="BTC-USDT",
            exchange="BINANCE",
            datetime=None,
            bid_price_1=45000.0,
            bid_volume_1=1.0,
            ask_price_1=45001.0,
            ask_volume_1=1.0
        )
        
        # 模拟下单方法
        self.strategy.buy = Mock(return_value=["test_order_id"])
        self.strategy.short = Mock(return_value=["test_order_id"])
        
        # 测试tick处理
        self.strategy.on_tick(tick)
        
        # 验证是否创建了正确数量的订单
        total_orders = len(self.strategy.long_orders_dict) + len(self.strategy.short_orders_dict)
        self.assertLessEqual(total_orders, self.strategy.max_open_orders * 2)

    def test_on_order(self):
        """测试订单状态更新处理"""
        self.strategy.calculate_grid_parameters()
        
        # 创建模拟订单
        order = OrderData(
            symbol="BTC-USDT",
            exchange="BINANCE",
            orderid="test_order_id",
            direction=1,  # 买入
            price=44000.0,
            volume=0.1,
            status=Status.ALLTRADED
        )
        
        # 添加到订单字典
        self.strategy.long_orders_dict["test_order_id"] = order.price
        
        # 模拟下单方法
        self.strategy.buy = Mock(return_value=["new_test_order_id"])
        self.strategy.short = Mock(return_value=["new_test_order_id"])
        
        # 测试订单完全成交
        self.strategy.on_order(order)
        
        # 验证订单是否被正确处理
        self.assertNotIn("test_order_id", self.strategy.long_orders_dict)
        self.assertEqual(self.strategy.trade_times, 1)

    def test_price_consistency(self):
        """测试价格类型一致性"""
        self.strategy.calculate_grid_parameters()
        
        # 验证价格字典中的键是否都是float类型
        for price in self.strategy.price_volume_dict.keys():
            self.assertIsInstance(price, float)
        
        # 验证订单字典中的价格是否都是float类型
        test_order_id = "test_order_id"
        test_price = 44000.0
        self.strategy.long_orders_dict[test_order_id] = test_price
        self.assertIsInstance(self.strategy.long_orders_dict[test_order_id], float)

if __name__ == '__main__':
    unittest.main() 