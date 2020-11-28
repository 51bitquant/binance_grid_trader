# -*- coding:utf-8 -*-
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


import json


class Config:

    def __init__(self):

        self.platform: str = "binance_spot"  # 交易的平台
        self.symbol:str = "BNBUSDT"  # 交易对.
        self.gap_percent: float = 0.01  # 网格变化交易的单位.
        self.api_key: str = None
        self.api_secret: str = None
        self.pass_phrase = None
        self.quantity:float = 1
        self.min_price =  0.0001
        self.min_qty = 0.01
        self.max_orders = 1
        self.proxy_host = ""  # proxy host
        self.proxy_port = 0  # proxy port


    def loads(self, config_file=None):
        """ Load config file.

        Args:
            config_file: config json file.
        """
        configures = {}
        if config_file:
            try:
                with open(config_file) as f:
                    data = f.read()
                    configures = json.loads(data)
            except Exception as e:
                print(e)
                exit(0)
            if not configures:
                print("config json file error!")
                exit(0)
        self._update(configures)

    def _update(self, update_fields):
        """
        更新update fields.
        :param update_fields:
        :return: None

        """

        for k, v in update_fields.items():
            setattr(self, k, v)

config = Config()