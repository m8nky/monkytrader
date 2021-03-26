telegramAPI = None
binanceAPI = None

def initGateway():
    # Initialize pushNotifier (Telegram).
    global telegramAPI
    from .telegram import Telegram
    telegramAPI = Telegram("monkytrader")
    # Initialize binance exchange.
    global binanceAPI
    from .binanceApi import BinanceAPI
    binanceAPI = BinanceAPI()
    binanceAPI.startUserStream()
