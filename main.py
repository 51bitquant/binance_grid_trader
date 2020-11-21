
"""
    币安推荐码:  返佣10%
    https://www.binancezh.pro/cn/register?ref=AIR1GC70

    币安合约推荐码: 返佣10%
    https://www.binancezh.com/cn/futures/ref/51bitquant

    if you don't have a binance account, you can use the invitation link to register one:
    https://www.binancezh.com/cn/futures/ref/51bitquant

    or use the inviation code: 51bitquant

    风险提示: 网格交易在单边行情的时候，会承受比较大的风险，请你了解整个代码的逻辑，然后再使用。
    RISK NOTE: Grid trading will endure great risk at trend market, please check the code before use it. USE AT YOUR OWN RISK.


"""

import time
import logging
from trader.binance_trader import BinanceTrader
from trader.binance_future_trader import BinanceFutureTrader
from utils import config

format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=format, filename='grid_trader_log.txt')
logger = logging.getLogger('binance')

if __name__ == '__main__':


    config.loads('./config.json')

    if config.platform == 'binance_spot':
        trader = BinanceTrader()
    else:
        trader = BinanceFutureTrader()
    orders = trader.http_client.cancel_open_orders(config.symbol)
    print(f"cancel orders: {orders}")

    while True:
        try:
            trader.grid_trader()
            time.sleep(20)

        except Exception as error:
            print(f"catch error: {error}")
            time.sleep(5)

