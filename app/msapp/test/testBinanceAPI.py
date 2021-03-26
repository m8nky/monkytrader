import logging
import unittest
from nose.plugins.attrib import attr
from decimal import Decimal
import simplejson as json

import msapp.gateway
from msapp.domain import Order

@attr('binance')
class TestBinanceAPI(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self._l = logging.getLogger(__name__)

    def setUp(self):
        msapp.gateway.initGateway()

    def tearDown(self):
        msapp.gateway.binanceAPI._bmt.stop_socket(msapp.gateway.binanceAPI._bmtConnKey)
        msapp.gateway.binanceAPI._bmt.close()
        msapp.gateway.binanceAPI._bmu.stop_socket(msapp.gateway.binanceAPI._bmuConnKey)
        msapp.gateway.binanceAPI._bmu.close()

    @attr('binance_fetchorders')
    def test_fetchorders(self):
        symbol = "BTCUSDT"
        try:
            orders = msapp.gateway.binanceAPI.getAllOrders(symbol=symbol)
            self._l.info(json.dumps([ order.toDict() for order in orders ], indent=2, ensure_ascii=False))
            self.assertGreaterEqual(len(orders), 1, "Failed to fetch orders, for this test ensure that at least one (canceled or other status) order is in place on binance.")
            orders = msapp.gateway.binanceAPI.getAllOrders(symbol=symbol, fromId=orders[-1].id())
            self._l.info(json.dumps([ order.toDict() for order in orders ], indent=2, ensure_ascii=False))
            self.assertEquals(len(orders), 1, f"Failed to fetch orders starting from id '{orders[-1].id()}'.")
        except Exception:
            self._l.exception("Fetching orders failed.")
            assert False

    @attr('binance_fetchtrades')
    def test_fetchtrades(self):
        symbol = "BTCUSDT"
        try:
            trades = msapp.gateway.binanceAPI.getTrades(symbol=symbol)
            self._l.info(json.dumps([ trade.toDict() for trade in trades ], indent=2, ensure_ascii=False))
            self.assertGreaterEqual(len(trades), 1, "Failed to fetch trades, for this test ensure that at least one trade has occurred.")
            trades = msapp.gateway.binanceAPI.getTrades(symbol=symbol, fromId=trades[-1].id())
            self._l.info(json.dumps([ trade.toDict() for trade in trades ], indent=2, ensure_ascii=False))
            self.assertEquals(len(trades), 1, f"Failed to fetch trades starting from id '{trades[-1].id()}'.")
        except Exception:
            self._l.exception("Fetching trades failed.")
            assert False

    @attr('binance_getprice')
    def test_getprice(self):
        msapp.gateway.binanceAPI.startTradeStream("BTCUSDT")
        import time
        time.sleep(5)
        price1 = msapp.gateway.binanceAPI.getCurrentPrice("BTCUSDT")
        print(price1)
        # 3 sec. should be enough to update trades from this pair. It's heavily used.
        time.sleep(3)
        price2 = msapp.gateway.binanceAPI.getCurrentPrice("BTCUSDT")
        print(price2)
        self.assertNotEquals(price1, price2, "Price should update over time.")

    @attr('binance_placetestorder')
    def test_placetestorder(self):
        try:
            symbolinfo = msapp.gateway.binanceAPI._getSymbolInfo("BTCUSDT")
            self._l.info(json.dumps(symbolinfo, indent=2, ensure_ascii=False))
            order = msapp.gateway.binanceAPI.placeLimitBuyOrder(symbol="BTCUSDT", quantity=Decimal('0.00333'), price=Decimal('3000.0'), isTest=True)
            self.assertFalse(order, "Placing test order should fail due to API Error MIN_NOTIONAL or similar.")
            order = msapp.gateway.binanceAPI.placeLimitBuyOrder(symbol="BTCUSDT", quantity=Decimal('0.00334'), price=Decimal('3000.0'), isTest=True)
            self.assertTrue(order, "Placing test order failed, but should work.")
        except Exception:
            self._l.exception("Placing test order failed.")
            assert False

    @attr('binance_orderplaceable')
    def test_orderplaceable(self):
        self.assertTrue(msapp.gateway.binanceAPI.isOrderPlaceable(symbol="BTCUSDT", tradeType="LIMIT_BUY", quantity=Decimal('0.003334'), price=Decimal('3000.0')))
        self.assertFalse(msapp.gateway.binanceAPI.isOrderPlaceable(symbol="BTCUSDT", tradeType="LIMIT_BUY", quantity=Decimal('0.003333'), price=Decimal('3000.0')))
        self.assertTrue(msapp.gateway.binanceAPI.isOrderPlaceable(symbol="BTCUSDT", tradeType="LIMIT_SELL", quantity=Decimal('0.003334'), price=Decimal('3000.0')))
        self.assertFalse(msapp.gateway.binanceAPI.isOrderPlaceable(symbol="BTCUSDT", tradeType="LIMIT_SELL", quantity=Decimal('0.003333'), price=Decimal('3000.0')))

    @attr('binance_placeorder')
    def test_placeorder(self):
        assert False, "Place real orders on the exchange! Disable this line to apply the test."
        try:
            symbolinfo = msapp.gateway.binanceAPI.getSymbolInfo("BTCUSDT")
            self._l.info(json.dumps(symbolinfo, indent=2, ensure_ascii=False))
            order = msapp.gateway.binanceAPI.placeLimitBuyOrder(symbol="BTCUSDT", quantity=Decimal('0.00334'), price=Decimal('3000.0'))
            self._l.info("Placed: " + json.dumps(order.toDict(), indent=2, ensure_ascii=False))
            self.assertEquals(order.status(), Order.STATUS_NEW, "Placing order failed..")
            cOrder = msapp.gateway.binanceAPI.cancelOrder(symbol="BTCUSDT", orderId=order.id())
            self._l.info("Canceled: " + json.dumps(cOrder.toDict(), indent=2, ensure_ascii=False))
            self.assertEquals(cOrder.status(), Order.STATUS_CANCELED, "Canceling order failed.")
        except Exception:
            self._l.exception("Placing real order.")
            assert False
