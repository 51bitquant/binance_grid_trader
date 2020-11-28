#  51bitquant网格交易策略

## 使用 how to use
1. 修改配置文件, config your config file.

```json
{
  "platform": "binance_spot",  
  "symbol": "BTCUSDT",
  "api_key": "replace your api key here",
  "api_secret": "replace your api secret here",
  "gap_percent": 0.001,
  "quantity": 0.001,
  "min_price": 0.01,
  "min_qty": 0.001,
  "max_orders": 1,
  "proxy_host": "127.0.0.1",
  "proxy_port": 1087
}

```

1. platform 是交易的平台, 填写 binance_spot 或者 binance_future,
   如果交易的是合约的，就填写binance_future.
2. symbol 交易对: BTCUSDT, BNBUSDT等
3. api_key : 从交易所获取
4. api_secret: 交易所获取
5. gap_percent: 网格交易的价格间隙
6. quantity : 每次下单的数量
7. min_price: 价格波动的最小单位, 用来计算价格精度： 如BTCUSDT 是0.01,
   BNBUSDT是0.0001, ETHUSDT 是0.01, 这个价格要从交易所查看，每个交易对不一样。
   
8. min_qty: 最小的下单量, 现货B要求最小下单是10USDT等值的币, 而对于合约来说,
   BTCUSDT要求是0.001个BTC
9. max_orders: 单边的下单量
10. proxy_host: 如果需要用代理的话，请填写你的代理 your proxy host, if you
    want proxy
11. proxy_port: 代理端口号 your proxy port for connecting to binance.


修改完配置文件后，用shell 命令运行下面的shell 命令:
> sh start.sh 

网格交易的原理视频讲解链接:
[https://www.bilibili.com/video/BV1Jg4y1v7vr/](https://www.bilibili.com/video/BV1Jg4y1v7vr/)

## 交易所注册推荐码

- OKEX 交易所注册推荐码, 手续费返佣20%
   - [https://www.okex.me/join/1847111798](https://www.okex.me/join/1847111798)

- 币安合约推荐码:返佣10%
   - [https://www.binancezh.com/cn/futures/ref/51bitquant](https://www.binancezh.com/cn/futures/ref/51bitquant)

## 网格交易策略使用行情
- 震荡行情
- 适合币圈的高波动率的品种
- 适合现货， 如果交易合约，需要注意防止极端行情爆仓。

## 服务器购买
推荐ucloud的服务器
- 价格便宜
- 网络速度和性能还不错
- 推荐链接如下：可以通过下面链接够买服务器，可以享受打折优惠:

[https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing](https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing)

视频讲解如下:
[https://www.bilibili.com/video/BV1eK4y147HT/](https://www.bilibili.com/video/BV1eK4y147HT/)


## 部署服务器
参考我的博客
- [https://www.jianshu.com/p/50fc54ca5ead](https://www.jianshu.com/p/50fc54ca5ead)
- [https://www.jianshu.com/p/61cb2a24a658](https://www.jianshu.com/p/61cb2a24a658)
- [https://www.jianshu.com/p/8c1afcbbe722](https://www.jianshu.com/p/8c1afcbbe722)


## linux 常用命令

- cd  # 是切换工作目录， 具体使用可以通过man 指令 | 指令 --help
- clear
- ls  # 列出当前文件夹的文件
- rm 文件名  # 删除文件
- rm -rf 文件夹 # 删除文件
- cp # 拷贝文件 copy 
- scp scp binance_grid_trader.zip ubuntu@xxx.xxx.xxx.xxx:/home/ubuntu
- pwd 
- mv  #  移动或者剪切文件
- ps -ef | grep main.py    # 查看进程
- kill 进程id  # 杀死当前进程

## 部署
直接把代码上传到服务器, 通过scp命令上传
- 先把代码压缩一下
- 通过一下命令上传到自己的服务器, **xxx.xxx.xxx.xxx**为你的服务器地址, **:/home/ubuntu**表示你上传到服务器的目录

> scp binance_grid_trader.zip ubuntu@xxx.xxx.xxx.xxx:/home/ubuntu

安装软件 sudo apt-get install 软件名称 | 库
> sudo apt-get install  unzip   # pip install requests
解压文件
>  unzip binance_grid_trader.zip  

进入该文件夹目录
> cd binance_grid_trader   

安装依赖包
> pip install -r requirements.txt  

执行运行脚本
> sh start.sh 

查看程序运行的id
> ps -ef | grep main.py

杀死进程, 关闭程序
> kill <进程ID> 

**linux服务器指令和网格策略实盘部署过程如下**
[https://www.bilibili.com/video/BV1mK411n7JW/](https://www.bilibili.com/video/BV1mK411n7JW/)

## 更多课程内容
请参考网易云课堂的视频
- [网易云课堂链接](https://www.jianshu.com/go-wild?ac=2&url=https%3A%2F%2Fstudy.163.com%2Fcourse%2FcourseMain.htm%3FcourseId%3D1209509824%26share%3D2%26shareId%3D480000001919830)
- 你也可以在网易云课堂直接搜索**51bitquant**可以找到课程视频。
## 联系我
可以添加我的微信，如果你有什么量化问题、python学习、课程咨询等方面的问题，都可以咨询我。

![51bitquant个人微信](https://upload-images.jianshu.io/upload_images/814550-f83c8302f2c4e344.jpg?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)



