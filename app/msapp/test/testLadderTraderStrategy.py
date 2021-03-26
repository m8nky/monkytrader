import logging
import unittest
from unittest import mock
from nose.plugins.attrib import attr
from decimal import Decimal
import re

import msapp.datamapper
import msapp.gateway
from msapp.gateway import initGateway
from msapp.datamapper import initDatastores
from msapp.domain.repository import Position
from msapp.gateway.binanceApi import BinanceAPI
from msapp.gateway.telegram import Telegram
from msapp.domain.service.tradingstrategy import LadderTradingStrategy

@attr('ladder')
class TestLadderTraderStrategy(unittest.TestCase):
    lastOrderId = -1
    lastTradeId = -1

    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self._l = logging.getLogger(__name__)

    def setUp(self):
        # Prune all test content from datastore.
        from msapp.datamapper.redisDB import RedisDB
        kvstore = RedisDB()
        _stores = {
            'position': "_laddertest",
            'order': "-",
            'trade': "-"
        }
        for store in _stores.keys():
            gc = kvstore._db.hkeys(store)
            gc = [ k.decode('utf-8') for k in gc if re.match(_stores[store], k.decode('utf-8')) is not None ]
            for k in gc:
                kvstore._db.hdel(store, k)
        TestLadderTraderStrategy.lastOrderId = -1
        TestLadderTraderStrategy.lastTradeId = -1

    def _positions(self):
        symbol = "BTCUSDT"
        positions = {
            'symbol': symbol,
            'positions': [
                {
                    'id': "_laddertest_t1",
                    'position': { 'type': "LONG_LADDER", 'high': { 'sellLimit': Decimal('11000') }, 'low': { 'buyLimit': Decimal('10000') }},
                    'symbol': symbol,
                    'volume': Decimal("0"),
                    'quoteVolume': Decimal("20"),
                    'orders': []
                },
                {
                    'id': "_laddertest_t2",
                    'position': { 'type': "LONG_LADDER", 'high': { 'sellLimit': Decimal('12000') }, 'low': { 'buyLimit': Decimal('11000') }},
                    'symbol': symbol,
                    'volume': Decimal("0"),
                    'quoteVolume': Decimal("20"),
                    'orders': []
                },
            ]
        }
        return positions

    def _order(self, symbol, side, price, origQty, status):
        TestLadderTraderStrategy.lastOrderId -= 1
        return {
            'symbol': symbol,
            'orderId': TestLadderTraderStrategy.lastOrderId,
            'orderListId': -1,
            'clientOrderId': 'web_0440d25b79714a118c62f8e9ed6bbc52',
            'price': str(price),
            'origQty': str(origQty),
            'executedQty': '0.00000000',
            'cummulativeQuoteQty': '0.00000000',
            'status': status,
            'timeInForce': 'GTC',
            'type': 'LIMIT',
            'side': side,
            'stopPrice': '0.00000000',
            'icebergQty': '0.00000000',
            'time': 1585855462553,
            'updateTime': 1585855462553,
            'isWorking': True,
            'origQuoteOrderQty': '0.00000000'
        }

    def _trade(self, orderId, symbol, side, qty, quoteQty):
        TestLadderTraderStrategy.lastTradeId -= 1
        trade = {
            'symbol': symbol,
            'id': TestLadderTraderStrategy.lastTradeId,
            'orderId': orderId,
            'orderListId': -1,
            'price': "0.00000000",
            'qty': str(qty),
            'quoteQty': str(quoteQty),
            'commission': '0.05970597',
            'commissionAsset': 'BNB',
            'time': 1585855462553,
            'isBuyer': True if side == "BUY" else False,
            'isMaker': True,
            'isBestMatch': True
        }
        return msapp.gateway.binanceAPI._assembleTrade(trade)

    @attr('ladder_placemissingorders')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'getCurrentPrice')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'placeLimitSellOrder')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'placeLimitBuyOrder')
    @mock.patch.object(msapp.gateway.telegram.Telegram, 'enabled')
    def test_placemissingorders(self, mock_telegramEnabled, mock_placeLimitBuyOrder, mock_placeLimitSellOrder, mock_getCurrentPrice):
        initGateway()
        initDatastores()
        def plso(*args, **kwargs):
            o = self._order(symbol=args[0], side="SELL", price=args[2], origQty=args[1], status="NEW")
            return msapp.gateway.binanceAPI._assembleOrder(o, filterRejectedExpired=True)
        def plbo(*args, **kwargs):
            o = self._order(symbol=args[0], side="BUY", price=args[2], origQty=args[1], status="NEW")
            return msapp.gateway.binanceAPI._assembleOrder(o, filterRejectedExpired=True)
        try:
            mock_telegramEnabled.return_value = False
            mock_placeLimitSellOrder.side_effect = plso
            mock_placeLimitBuyOrder.side_effect = plbo
            symbol = self._positions()['symbol']
            positions = [ Position.fromDict(p) for p in self._positions()['positions'] ]
            lts = LadderTradingStrategy("BTCUSDT", positions)
            # Start with price between first and second ladder.
            mock_getCurrentPrice.return_value = Decimal("10500")
            lts._placeMissingOrders()
            mock_getCurrentPrice.assert_called_with(symbol)
            for p in positions:
                p._loadOrders()
            self.assertDictEqual(positions[0]._orders[0].toDict(), {'orderId': -3, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'BUY', 'price': Decimal('10000'), 'origQuantity': Decimal('20')}, "Order content mismatch.")
            # Now set price between the two positions.
            mock_getCurrentPrice.return_value = Decimal("11500")
            lts._placeMissingOrders()
            for p in positions:
                p._loadOrders()
            self.assertDictEqual(positions[0]._orders[0].toDict(), {'orderId': -3, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'BUY', 'price': Decimal('10000'), 'origQuantity': Decimal('20')}, "Order content mismatch.")
            self.assertDictEqual(positions[1]._orders[0].toDict(), {'orderId': -5, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'BUY', 'price': Decimal('11000'), 'origQuantity': Decimal('20')}, "Order content mismatch.")
            # Update position volume to force creating sell orders.
            positions[0]._orders[0]._status = "FILLED"
            positions[0]._orders[0].save()
            positions[0]._volume = Decimal("0.002")
            positions[0]._quoteVolume = Decimal("0")
            mock_getCurrentPrice.return_value = Decimal("10500")
            lts._placeMissingOrders()
            for p in positions:
                p._loadOrders()
            self.assertDictEqual(positions[0]._orders[1].toDict(), {'orderId': -7, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'SELL', 'price': Decimal('11000'), 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
        except Exception:
            raise
        finally:
            msapp.gateway.binanceAPI.shutdown()

    @attr('ladder_tradeevent')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'getCurrentPrice')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'placeLimitSellOrder')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'placeLimitBuyOrder')
    @mock.patch.object(msapp.gateway.binanceApi.BinanceAPI, 'getOrder')
    @mock.patch.object(msapp.gateway.telegram.Telegram, 'enabled')
    def test_tradeevent(self, mock_telegramEnabled, mock_getOrder, mock_placeLimitBuyOrder, mock_placeLimitSellOrder, mock_getCurrentPrice):
        initGateway()
        initDatastores()
        def plso(*args, **kwargs):
            o = self._order(symbol=args[0], side="SELL", price=args[2], origQty=args[1], status="NEW")
            return msapp.gateway.binanceAPI._assembleOrder(o, filterRejectedExpired=True)
        def plbo(*args, **kwargs):
            o = self._order(symbol=args[0], side="BUY", price=args[2], origQty=args[1], status="NEW")
            return msapp.gateway.binanceAPI._assembleOrder(o, filterRejectedExpired=True)
        def geto(*args, **kwargs):
            o = self._order(symbol=args[0], side=_side, price=_price, origQty=_origQty, status=_status)
            o['orderId'] = args[1]
            return msapp.gateway.binanceAPI._assembleOrder(o, filterRejectedExpired=False)
        try:
            mock_telegramEnabled.return_value = False
            mock_getOrder.side_effect = geto
            mock_placeLimitSellOrder.side_effect = plso
            mock_placeLimitBuyOrder.side_effect = plbo
            mock_getCurrentPrice.return_value = Decimal("10001")
            symbol = self._positions()['symbol']
            positions = [ Position.fromDict(p) for p in self._positions()['positions'] ]
            lts = LadderTradingStrategy("BTCUSDT", positions)
            # Well ok so far, inject some trades.
            trade = self._trade(-3, symbol, "BUY", Decimal("0.002"), Decimal("20"))
            _side = "BUY"
            _price = trade._price
            _origQty = trade._quantity
            _status = "FILLED"
            print(trade.toDict())
            # 1. Place initial orders.
            mock_getCurrentPrice.return_value = Decimal("10001")
            lts._placeMissingOrders()
            # 2. Expect trade (BUY 0.002) of lower ladder. Automatic (SELL 0.002 at 11000) order must be generated.
            mock_getCurrentPrice.return_value = Decimal("10001")
            lts._tradeEvent(trade)
            # Validate first order closed (filled) and 2nd order in place.
            self.assertDictEqual(positions[0]._orders[0].toDict(), {'orderId': -3, 'symbol': 'BTCUSDT', 'status': 'FILLED', 'timestamp': 1585855462553, 'side': 'BUY', 'price': trade._price, 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
            self.assertDictEqual(positions[0]._orders[1].toDict(), {'orderId': -6, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'SELL', 'price': Decimal('11000'), 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
            # Validate updated position volumes.
            self.assertDictEqual(positions[0].toDict(), {'id': '_laddertest_t1', 'position': {'type': 'LONG_LADDER', 'high': {'sellLimit': Decimal('11000')}, 'low': {'buyLimit': Decimal('10000')}}, 'symbol': 'BTCUSDT', 'volume': Decimal('0.002'), 'quoteVolume': Decimal('0'), 'orders': [-3, -6]}, "Position volume incorrect.")
            # 3. Simulate price drop, should have no effect.
            mock_getCurrentPrice.return_value = Decimal("9999")
            lts._placeMissingOrders()
            # Validate first order closed (filled) and 2nd order in place.
            self.assertDictEqual(positions[0]._orders[0].toDict(), {'orderId': -3, 'symbol': 'BTCUSDT', 'status': 'FILLED', 'timestamp': 1585855462553, 'side': 'BUY', 'price': trade._price, 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
            self.assertDictEqual(positions[0]._orders[1].toDict(), {'orderId': -6, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'SELL', 'price': Decimal('11000'), 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
            # Validate updated position volumes.
            self.assertDictEqual(positions[0].toDict(), {'id': '_laddertest_t1', 'position': {'type': 'LONG_LADDER', 'high': {'sellLimit': Decimal('11000')}, 'low': {'buyLimit': Decimal('10000')}}, 'symbol': 'BTCUSDT', 'volume': Decimal('0.002'), 'quoteVolume': Decimal('0'), 'orders': [-3, -6]}, "Position volume incorrect.")
            # 4. Simulate price between 1st and 2nd ladder.
            mock_getCurrentPrice.return_value = Decimal("11001")
            trade = self._trade(-6, symbol, "SELL", Decimal('0.002'), Decimal(Decimal('0.002') * Decimal('11000')).quantize(Decimal('0.000001')))
            _side = "SELL"
            _price = trade._price
            _origQty = trade._quantity
            _status = "FILLED"
            lts._tradeEvent(trade)
            # Validate 2nd order SELL filled and 3rd order BUY placed.
            self.assertDictEqual(positions[0]._orders[1].toDict(), {'orderId': -6, 'symbol': 'BTCUSDT', 'status': 'FILLED', 'timestamp': 1585855462553, 'side': 'SELL', 'price': Decimal('0E-8'), 'origQuantity': Decimal('0.002')}, "Order content mismatch.")
            self.assertDictEqual(positions[0]._orders[2].toDict(), {'orderId': -9, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'BUY', 'price': Decimal('10000'), 'origQuantity': Decimal('0.002200')}, "Order content mismatch.")
            # Validate updated position volume.
            self.assertDictEqual(positions[0].toDict(), {'id': '_laddertest_t1', 'position': {'type': 'LONG_LADDER', 'high': {'sellLimit': Decimal('11000')}, 'low': {'buyLimit': Decimal('10000')}}, 'symbol': 'BTCUSDT', 'volume': Decimal('0.000'), 'quoteVolume': Decimal('22.000000'), 'orders': [-3, -6, -9]}, "Position volume incorrect.")
            # Validate 4th order BUY placed.
            self.assertDictEqual(positions[1]._orders[0].toDict(), {'orderId': -11, 'symbol': 'BTCUSDT', 'status': 'NEW', 'timestamp': 1585855462553, 'side': 'BUY', 'price': Decimal('11000'), 'origQuantity': Decimal('0.001818')}, "Order content mismatch.")
            # Validate 2nd position volume not updated.
            self.assertDictEqual(positions[1].toDict(), {'id': '_laddertest_t2', 'position': {'type': 'LONG_LADDER', 'high': {'sellLimit': Decimal('12000')}, 'low': {'buyLimit': Decimal('11000')}}, 'symbol': 'BTCUSDT', 'volume': Decimal('0'), 'quoteVolume': Decimal('20'), 'orders': [-11]}, "Position volume incorrect.")
        except Exception:
            raise
        finally:
            msapp.gateway.binanceAPI.shutdown()

    #TODO: Test bootstrap for closing of manually canceled and filled orders.
