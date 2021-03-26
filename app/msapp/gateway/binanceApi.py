import logging
import simplejson as json
from binance.client import Client
from binance.websockets import BinanceSocketManager
from twisted.internet import reactor
from multiprocessing import Manager
from decimal import Decimal

from msapp.domain import Trade
from msapp.domain import Order
from msapp.domain.mscore import Task
from msapp.domain.mscore import TaskQueue
from msapp import config

class BinanceAPI:
    _self = None

    def __init__(self):
        BinanceAPI._self = self
        self._l = logging.getLogger(__name__)
        # Track prices of symbols.
        self._mpManager = Manager()
        self._symbolCurrentPricesMutex = self._mpManager.Lock()
        self._symbolCurrentPrices = self._mpManager.dict()
        # Symbol info cache.
        self._symbolInfo = {}
        # Execution event transporter.
        self._execReportQueue = TaskQueue()
        # Initialize binance client.
        self._client = Client(config.c['binance']['apikey'], config.c['binance']['apisecret'])
        # Initialize stream connections.
        self._bmu = BinanceSocketManager(self._client, user_timeout=60)
        self._bmuConnKey = None
        self._bmt = BinanceSocketManager(self._client, user_timeout=60)
        self._bmtConnKey = None

    def startTradeStream(self, symbol: str):
        self._symbolCurrentPricesMutex.acquire()
        try:
            self._symbolCurrentPrices[symbol] = None
        except Exception:
            self._l.exception("ERROR: Initializing symbol price tracker.")
        finally:
            self._symbolCurrentPricesMutex.release()
        self._bmtConnKey = self._bmt.start_trade_socket(symbol, BinanceAPI._processEvent)
        self._bmt.start()

    def startUserStream(self):
        self._bmuConnKey = self._bmu.start_user_socket(BinanceAPI._processEvent)
        self._bmu.start()

    def shutdown(self):
        self._bmt.stop_socket(self._bmtConnKey)
        self._bmt.close()
        self._bmu.stop_socket(self._bmuConnKey)
        self._bmu.close()
        reactor.stop()
        self._execReportQueue = []

    def registerERqueue(self):
        self._l.debug("DISABLED: Registering new tradeEvents listener to binance does not work currently. Shared event queue is returned instead.")
        return self._execReportQueue

    def getCurrentPrice(self, symbol: str):
        self._symbolCurrentPricesMutex.acquire()
        price = None
        try:
            price = self._symbolCurrentPrices[symbol]
        except Exception:
            self._l.exception(f"ERROR: Symbol not found {symbol}.")
        finally:
            self._symbolCurrentPricesMutex.release()
        return price

    def getAllOrders(self, symbol: str, fromId: int = None, limit: int = 500, filterRejectedExpired: bool = True):
        # TODO: Pagination!
        if fromId is None:
            orders = self._client.get_all_orders(symbol=symbol, limit=limit)
        else:
            orders = self._client.get_all_orders(symbol=symbol, orderId=fromId, limit=limit)
        self._l.debug(json.dumps(orders, indent=4, ensure_ascii=False))
        result = []
        for o in orders:
            order = self._assembleOrder(o, filterRejectedExpired)
            if order is not None:
                result.append(order)
        return result

    def getOrder(self, symbol: str, orderId: int):
        bOrder = self._client.get_order(symbol=symbol, orderId=orderId)
        self._l.debug(json.dumps(bOrder, indent=4, ensure_ascii=False))
        return self._assembleOrder(bOrder, filterRejectedExpired=False)

    def isOrderPlaceable(self, symbol: str, tradeType: str, quantity: Decimal, price: Decimal):
        assert tradeType in [ "LIMIT_BUY", "LIMIT_SELL" ], f"Unknown tradeType '{tradeType}'"
        # Check quoteVolume is the minimum required for placing a trade.
        symbolInfo = self._getSymbolInfo(symbol)
        minNotional = Decimal([ f['minNotional'] for f in symbolInfo['filters'] if f['filterType'] == "MIN_NOTIONAL" ][0])
        self._l.debug(f"{minNotional} {quantity} {price} {quantity * price}")
        if minNotional > price * quantity:
            self._l.warning("Quote volume too small: " + str(price * quantity) + " < " + str(minNotional))
            return False
        return self.placeLimitBuyOrder(symbol, quantity, price, isTest=True) if tradeType == "LIMIT_BUY" else self.placeLimitSellOrder(symbol, quantity, price, isTest=True)

    def placeLimitBuyOrder(self, symbol: str, quantity: Decimal, price: Decimal, isTest: bool = False):
        return self._placeLimitOrder(symbol=symbol, side=Client.SIDE_BUY, quantity=quantity, price=price, isTest=isTest)

    def placeLimitSellOrder(self, symbol: str, quantity: Decimal, price: Decimal, isTest: bool = False):
        return self._placeLimitOrder(symbol=symbol, side=Client.SIDE_SELL, quantity=quantity, price=price, isTest=isTest)

    def cancelOrder(self, symbol: str, orderId: int):
        bOrder = self._client.cancel_order(symbol=symbol, orderId=orderId)
        self._l.debug(json.dumps(bOrder, indent=2, ensure_ascii=False))
        return self._assembleOrder(bOrder, filterRejectedExpired=False)

    def getTrades(self, symbol: str, fromId: int = None, limit: int = 500):
        # TODO: Pagination!
        if fromId is None:
            trades = self._client.get_my_trades(symbol=symbol, limit=limit)
        else:
            trades = self._client.get_my_trades(symbol=symbol, fromId=fromId, limit=limit)
        self._l.debug(json.dumps(trades, indent=4, ensure_ascii=False))
        result = []
        for t in trades:
            # Assemble trade object.
            trade = self._assembleTrade(t)
            result.append(trade)
        return result

    def _getSymbolInfo(self, symbol: str):
        if symbol not in self._symbolInfo:
            self._symbolInfo[symbol] = self._client.get_symbol_info(symbol)
            self._l.debug(f"Fetched symbol info for '{symbol}': " + json.dumps(self._symbolInfo[symbol], indent=2, ensure_ascii=False))
        return self._symbolInfo[symbol]

    def _placeLimitOrder(self, symbol: str, side: str, quantity: Decimal, price: Decimal, isTest: bool):
        qty = str(quantity)
        prc = str(price)
        if isTest:
            try:
                res = self._client.create_test_order(symbol=symbol, side=side, type=Client.ORDER_TYPE_LIMIT, timeInForce=Client.TIME_IN_FORCE_GTC, quantity=qty, price=prc)
                assert type(res) is dict and len(res) == 0, "ERROR: Placing test order failed."
            except Exception:
                self._l.exception("Placing test order failed.")
                return False
            return True
        bOrder = self._client.create_order(symbol=symbol, side=side, type=Client.ORDER_TYPE_LIMIT, timeInForce=Client.TIME_IN_FORCE_GTC, quantity=qty, price=prc)
        self._l.info(f"Placed new order: {bOrder['orderId']}")
        order = self._assembleOrder(bOrder, filterRejectedExpired=True)
        assert order is not None, "ERROR: Placing or assembling order failed."
        self._l.debug(json.dumps(order.toDict(), indent=2, ensure_ascii=False))
        return order

    def _assembleOrder(self, binanceOrder: dict, filterRejectedExpired: bool):
        # Remap order status.
        _osMap = {
            'NEW': Order.STATUS_NEW,
            'PARTIALLY_FILLED': Order.STATUS_PARTIALLY_FILLED,
            'FILLED': Order.STATUS_FILLED,
            'CANCELED': Order.STATUS_CANCELED,
            'REJECTED': Order.STATUS_REJECTED,
            'EXPIRED': Order.STATUS_EXPIRED
        }
        orderStatus = _osMap.get(binanceOrder['status'], None)
        assert orderStatus is not None, f"ERROR: Execution type '{binanceOrder['status']}' might lead to malfunction. Abort trading."
        # Ignore rejected orders.
        if filterRejectedExpired and orderStatus == Order.STATUS_REJECTED:
            self._l.debug(f"REJECTED order {binanceOrder['orderId']} found but ignored.")
            return None
        if filterRejectedExpired and orderStatus == Order.STATUS_EXPIRED and Decimal(binanceOrder['executedQty']).is_zero():
            self._l.debug(f"EXPIRED order {binanceOrder['orderId']} found but ignored due to executed price is zero.")
            return None
        # Find time field, depending on source its different.
        orderTime = binanceOrder['time'] if 'time' in binanceOrder else binanceOrder['transactTime'] if 'transactTime' in binanceOrder else None
        # Assemble order object.
        order = Order(
            orderId=binanceOrder['orderId'],
            symbol=binanceOrder['symbol'],
            status=orderStatus,
            timestamp=orderTime,
            side=Order.SIDE_BUY if binanceOrder['side'] == "BUY" else Order.SIDE_SELL,
            price=Decimal(binanceOrder['price']),
            origQuantity=Decimal(binanceOrder['origQty'])
        )
        return order

    def _assembleTrade(self, binanceTrade: dict):
        trade = None
        if 'id' in binanceTrade:
            trade = Trade(
                tradeId=binanceTrade['id'],
                orderId=binanceTrade['orderId'],
                symbol=binanceTrade['symbol'],
                timestamp=binanceTrade['time'],
                side=Trade.SIDE_BUY if binanceTrade['isBuyer'] is True else Trade.SIDE_SELL,
                price=Decimal(binanceTrade['price']),
                quantity=Decimal(binanceTrade['qty']),
                quoteQuantity=Decimal(binanceTrade['quoteQty']),
                commissionAmount=Decimal(binanceTrade['commission']),
                commissionAsset=binanceTrade['commissionAsset'])
        else:
            trade = Trade(
                tradeId=binanceTrade['t'],
                orderId=binanceTrade['i'],
                symbol=binanceTrade['s'],
                timestamp=binanceTrade['T'],
                side=Trade.SIDE_BUY if binanceTrade['S'] == "BUY" else Trade.SIDE_SELL,
                price=Decimal(binanceTrade['L']),
                quantity=Decimal(binanceTrade['l']),
                quoteQuantity=Decimal(binanceTrade['Y']),
                commissionAmount=Decimal(binanceTrade['n']),
                commissionAsset=binanceTrade['N'])
        assert trade is not None
        return trade

    def _notifyERqueue(self, trade: Trade):
        task = Task(trade.toDict())
        self._execReportQueue.add(task.toDict())

    @staticmethod
    def _processEvent(msg):
        _l = logging.getLogger(__name__)
        if msg['e'] == "error":
            error = "ERROR: Binance stream socket closed unexpectedly with '" + msg['m'] + "'."
            _l.error(error)
            raise Exception(error)
        elif msg['e'] == 'trade':
            BinanceAPI._tradeEvent(msg)
        elif msg['e'] == 'executionReport':
            _l.warning("Entered executionReport: " + json.dumps(msg, indent=2, ensure_ascii=False))
            BinanceAPI._executionReportEvent(msg)
        else:
            _l.warning("Unhandled event type: " + msg['e'])
            _l.warning(json.dumps(msg, indent=2, ensure_ascii=False))

    @staticmethod
    def _tradeEvent(msg):
        '''
        "e": "trade",
        "E": 1585157254420,
        "s": "BTCUSDT",
        "t": 279570946,
        "p": "6668.07000000",
        "q": "0.00254600",
        "b": 1629707385,
        "a": 1629707430,
        "T": 1585157254418,
        "m": true,
        "M": true
        '''
        symbol = msg['s']
        price = Decimal(msg['p'])
        BinanceAPI._self._symbolCurrentPricesMutex.acquire()
        try:
            BinanceAPI._self._symbolCurrentPrices[symbol] = price
        except Exception:
            _l = logging.getLogger(__name__)
            _l.exception("ERROR: Initializing symbol price tracker.")
        finally:
            BinanceAPI._self._symbolCurrentPricesMutex.release()

    @staticmethod
    def _executionReportEvent(msg):
        '''
        "e": "executionReport",        // Event type
        "E": 1499405658658,            // Event time
        "s": "ETHBTC",                 // Symbol
        "c": "mUvoqJxFIILMdfAW5iGSOW", // Client order ID
        "S": "BUY",                    // Side
        "o": "LIMIT",                  // Order type
        "f": "GTC",                    // Time in force
        "q": "1.00000000",             // Order quantity
        "p": "0.10264410",             // Order price
        "P": "0.00000000",             // Stop price
        "F": "0.00000000",             // Iceberg quantity
        "g": -1,                       // OrderListId
        "C": null,                     // Original client order ID; This is the ID of the order being canceled
        "x": "NEW",                    // Current execution type
        "X": "NEW",                    // Current order status
        "r": "NONE",                   // Order reject reason; will be an error code.
        "i": 4293153,                  // Order ID
        "l": "0.00000000",             // Last executed quantity
        "z": "0.00000000",             // Cumulative filled quantity
        "L": "0.00000000",             // Last executed price
        "n": "0",                      // Commission amount
        "N": null,                     // Commission asset
        "T": 1499405658657,            // Transaction time
        "t": -1,                       // Trade ID
        "I": 8641984,                  // Ignore
        "w": true,                     // Is the order on the book?
        "m": false,                    // Is this trade the maker side?
        "M": false,                    // Ignore
        "O": 1499405658657,            // Order creation time
        "Z": "0.00000000",             // Cumulative quote asset transacted quantity
        "Y": "0.00000000"              // Last quote asset transacted quantity (i.e. lastPrice * lastQty),
        "Q": "0.00000000"              // Quote Order Qty
        '''
        # Filter trade events only.
        if not msg['x'] == "TRADE":
            return
        assert msg['t'] > 0, f"ERROR: Trade ID '{msg['t']}' is invalid."
        # Assemble trade object.
        trade = BinanceAPI._self._assembleTrade(msg)
        BinanceAPI._self._notifyERqueue(trade)

'''
  These are execution report examples.
  1. Create and canceled order.
  2. Create an order, and get filled.

1.a) Create order.
{
  "e": "executionReport",
  "E": 1587307010198,
  "s": "BTCUSDT",
  "c": "web_122dda2d19564e8cb0a6556dbb870f12",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "0.00150000",
  "p": "7080.00000000",
  "P": "0.00000000",
  "F": "0.00000000",
  "g": -1,
  "C": "",
  "x": "NEW",
  "X": "NEW",
  "r": "NONE",
  "i": 1875717234,
  "l": "0.00000000",
  "z": "0.00000000",
  "L": "0.00000000",
  "n": "0",
  "N": null,
  "T": 1587307010197,
  "t": -1,
  "I": 4034418135,
  "w": true,
  "m": false,
  "M": false,
  "O": 1587307010197,
  "Z": "0.00000000",
  "Y": "0.00000000",
  "Q": "0.00000000"
}

1.b) Cancel order.
{
  "e": "executionReport",
  "E": 1587307096811,
  "s": "BTCUSDT",
  "c": "web_104dd6bfaa06437095d36a09126badf3",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "0.00150000",
  "p": "7080.00000000",
  "P": "0.00000000",
  "F": "0.00000000",
  "g": -1,
  "C": "web_122dda2d19564e8cb0a6556dbb870f12",
  "x": "CANCELED",
  "X": "CANCELED",
  "r": "NONE",
  "i": 1875717234,
  "l": "0.00000000",
  "z": "0.00000000",
  "L": "0.00000000",
  "n": "0",
  "N": null,
  "T": 1587307096809,
  "t": -1,
  "I": 4034436763,
  "w": false,
  "m": false,
  "M": false,
  "O": 1587307010197,
  "Z": "0.00000000",
  "Y": "0.00000000",
  "Q": "0.00000000"
}

2.a) Create order.
{
  "e": "executionReport",
  "E": 1587307099267,
  "s": "BTCUSDT",
  "c": "web_0f74ae19ca0a4958bf2e14decaecdc5b",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "0.00150000",
  "p": "7090.00000000",
  "P": "0.00000000",
  "F": "0.00000000",
  "g": -1,
  "C": "",
  "x": "NEW",
  "X": "NEW",
  "r": "NONE",
  "i": 1875726561,
  "l": "0.00000000",
  "z": "0.00000000",
  "L": "0.00000000",
  "n": "0",
  "N": null,
  "T": 1587307099265,
  "t": -1,
  "I": 4034437290,
  "w": true,
  "m": false,
  "M": false,
  "O": 1587307099265,
  "Z": "0.00000000",
  "Y": "0.00000000",
  "Q": "0.00000000"
}

2.b) Order filled trade.
{
  "e": "executionReport",
  "E": 1587307135823,
  "s": "BTCUSDT",
  "c": "web_0f74ae19ca0a4958bf2e14decaecdc5b",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "0.00150000",
  "p": "7090.00000000",
  "P": "0.00000000",
  "F": "0.00000000",
  "g": -1,
  "C": "",
  "x": "TRADE",
  "X": "FILLED",
  "r": "NONE",
  "i": 1875726561,
  "l": "0.00150000",
  "z": "0.00150000",
  "L": "7090.00000000",
  "n": "0.00049761",
  "N": "BNB",
  "T": 1587307135821,
  "t": 297145239,
  "I": 4034442437,
  "w": false,
  "m": true,
  "M": true,
  "O": 1587307099265,
  "Z": "10.63500000",
  "Y": "10.63500000",
  "Q": "0.00000000"
}
'''
