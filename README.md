# 51bitquant网格交易策略

# 交易所注册推荐码

- OKEX 交易所注册推荐码, 手续费返佣20%
   - https://www.okex.me/join/1847111798

- 币安现货推荐码：返佣20%
   - https://www.binancezh.com/cn/register?ref=ESE80ESH

- 币安合约推荐码:返佣10%
   - https://www.binancezh.com/cn/futures/ref/51bitquant


代码获取方式： 网易云课堂，或者联系bitquant51， 回复：网格交易代码
网格交易: 适合币圈的高波动率的品种，适合现货， 如果交易合约，需要注意防止极端行情爆仓。

## 部署服务器
购买服务器，可以参考一下链接: 
通过这个网站注册购买服务器: https://passport.ucloud.cn/?invitation_code=C1x2EA81CD79B8C
或者直接通过这个地址购买: https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing

# 购买地址

https://www.ucloud.cn/site/global.html?invitation_code=C1x2EA81CD79B8C#dongjing

# 博客地址
https://www.jianshu.com/p/50fc54ca5ead

# linux 常用命令

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
