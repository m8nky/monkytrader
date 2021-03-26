import logging
import ulid
from decimal import Decimal
import time

import msapp.datamapper
from msapp.domain import Order
from msapp.domain import Trade

class Position:
    TYPE_LONG_LADDER = "LONG_LADDER"

    @staticmethod
    def fromDict(data: dict):
        o = Position(data['id'])
        o._position = data['position']
        o._symbol = data['symbol']
        o._volume = data['volume']
        o._quoteVolume = data['quoteVolume']
        o._orders = [ Order(oid) for oid in data['orders'] ]
        return o

    @staticmethod
    def createLongLadder(symbol: str, highSellLimit: Decimal, lowBuyLimit: Decimal, volume: Decimal, quoteVolume: Decimal):
        position = {
            'type': Position.TYPE_LONG_LADDER,
            'high': {
                'sellLimit': highSellLimit
            },
            'low': {
                'buyLimit': lowBuyLimit
            }
        }
        o = Position(id=None, symbol=symbol, position=position, volume=volume, quoteVolume=quoteVolume)
        return o

    def __init__(self, id: str = None, symbol: str = None, position: dict = None, volume: Decimal = None, quoteVolume: Decimal = None):
        self._l = logging.getLogger(__name__)
        forceSleep = True if id is None else False
        self._id = ulid.ulid().lower() if id is None else id
        if forceSleep:
            # Sleep one ms to ensure lexicographically sortable position IDs.
            time.sleep(0.001)
        self._symbol = symbol
        self._position = position
        self._volume = volume
        self._quoteVolume = quoteVolume
        self._orders = []
        self._ordersLoaded = False

    def save(self):
        msapp.datamapper.positionstore.save(self)

    def id(self):
        return self._id

    def symbol(self):
        return self._symbol

    def volume(self):
        return self._volume

    def quoteVolume(self):
        return self._quoteVolume

    def calculateMaxBuyVolume(self, orderPrice: Decimal):
        # Calculate buy volume with fixed precision of 6.
        return Decimal(self._quoteVolume / orderPrice).quantize(Decimal('.000001'))

    def position(self):
        return self._position

    def updatePositionVolume(self, trade: Trade):
        orders = [ o.id() for o in self._orders ]
        if trade.orderId() in orders:
            if trade.side() == Trade.SIDE_BUY:
                self._quoteVolume -= trade.quoteQuantity()
                if self._quoteVolume.is_signed():
                    self._quoteVolume = Decimal("0.0")
                self._volume += trade.quantity()
            else:
                self._quoteVolume += trade.quoteQuantity()
                self._volume -= trade.quantity()
                if self._volume.is_signed():
                    self._volume = Decimal("0.0")

    def assignOrder(self, order: Order):
        oid = order.id()
        for e in self._orders:
            if e.id() == oid:
                self._l.error(f"Order with '{oid}' is already assigned to position '{self._id}'.")
                return False
        self._orders.append(order)
        return True

    def getOrder(self, orderId: int):
        self._loadOrders(force=False)
        for o in self._orders:
            if o.id() == orderId:
                return o
        return None

    def openOrders(self):
        self._loadOrders(force=False)
        return [ o for o in self._orders if not o.isClosed() ]

    def toDict(self):
        data = {
            'id': self._id,
            'position': self._position,
            'symbol': self._symbol,
            'volume': self._volume,
            'quoteVolume': self._quoteVolume,
            'orders': [ o.id() for o in self._orders ]
        }
        return data

    def toDictWithFullOrders(self):
        self._loadOrders(force=False)
        data = {
            'id': self._id,
            'position': self._position,
            'symbol': self._symbol,
            'volume': self._volume,
            'quoteVolume': self._quoteVolume,
            'orders': [ o.toDict() for o in self._orders ]
        }
        return data

    def _loadOrders(self, force: bool = False):
        if not self._ordersLoaded or force:
            self._l.debug(f"Updating orders from datastore for position '{self._id}'.")
            for o in self._orders:
                o.updateFromStore()
        self._ordersLoaded = True
