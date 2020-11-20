
"""

    OKEX 交易所注册推荐码, 手续费返佣20%.
    https://www.okex.me/join/1847111798

    币安推荐码:  返佣20%
    https://www.binancezh.com/cn/register?ref=ESE80ESH

    币安合约推荐码: 返佣10%
    https://www.binancezh.com/cn/futures/ref/51bitquant

    代码获取方式： 网易云课堂，或者联系bitquant51， 回复：网格交易代码

    网格交易: 适合币圈的高波动率的品种，适合现货， 如果交易合约，需要注意防止极端行情爆仓。


    服务器购买地址: https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing
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
    binance_trader = BinanceFutureTrader() # BinanceTrader()
    orders = binance_trader.http_client.cancel_open_orders(config.symbol)
    print(f"cancel orders: {orders}")

    while True:
        try:
            binance_trader.grid_trader()
            time.sleep(20)

        except Exception as error:
            print(f"catch error: {error}")
            time.sleep(5)

