orderstore = None
tradestore = None
positionstore = None
tradingconfig = None
# Not needed, but Task asks for existence.
taskstore = None

def initDatastores():
    global orderstore
    global tradestore
    global positionstore
    global tradingconfig
    from .redisDB import RedisDB
    kvstore = RedisDB()
    from .orderStore import OrderStore
    orderstore = OrderStore(kvstore)
    from .tradeStore import TradeStore
    tradestore = TradeStore(kvstore)
    from .positionStore import PositionStore
    positionstore = PositionStore(kvstore)
    from .tradingConfig import TradingConfig
    tradingconfig = TradingConfig(kvstore)
