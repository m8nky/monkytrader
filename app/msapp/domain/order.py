import logging
from decimal import Decimal

import msapp.datamapper

class Order:
    SIDE_BUY = 'BUY'
    SIDE_SELL = 'SELL'

    STATUS_NEW = 'NEW'
    STATUS_PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    STATUS_FILLED = 'FILLED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_EXPIRED = 'EXPIRED'

    @staticmethod
    def fromDict(data: dict):
        o = Order(data['orderId'])
        o._symbol = data['symbol']
        o._status = data['status']
        o._timestamp = data['timestamp']
        o._side = data['side']
        o._price = data['price']
        o._origQuantity = data['origQuantity']
        return o

    def __init__(self, orderId: str,
                 symbol: str = None,
                 status: str = None,
                 timestamp: int = None,
                 side: str = None,
                 price: Decimal = None,
                 origQuantity: Decimal = None):
        self._l = logging.getLogger(__name__)
        self._orderId = orderId
        self._symbol = symbol
        self._status = status
        self._timestamp = timestamp
        self._side = side
        self._price = price
        self._origQuantity = origQuantity

    def save(self):
        msapp.datamapper.orderstore.save(self)

    def updateFromStore(self):
        o = msapp.datamapper.orderstore.load(self.id())
        self.update(o)

    def id(self):
        return self._orderId

    def status(self):
        return self._status

    def setStatus(self, status: str):
        assert status in [ Order.STATUS_CANCELED, Order.STATUS_EXPIRED, Order.STATUS_FILLED, Order.STATUS_NEW, Order.STATUS_PARTIALLY_FILLED, Order.STATUS_REJECTED ]
        self._status = status

    def isClosed(self):
        return self._status in [ Order.STATUS_FILLED, Order.STATUS_EXPIRED, Order.STATUS_CANCELED, Order.STATUS_REJECTED ]

    def update(self, order):
        assert isinstance(order, Order), f"ERROR: Parameter 'order' is not an Order object."
        assert self._orderId == order._orderId, f"ERROR: Id mismatch for updating order {self._orderId} != {order._orderId}."
        self._symbol = order._symbol
        self._status = order._status
        # Avoid deleting existing timestamp, because some exchange command might not deliver one, e.g. Cancel order on Binance.
        self._timestamp = order._timestamp if order._timestamp is not None else self._timestamp
        self._side = order._side
        self._price = order._price
        self._origQuantity = order._origQuantity

    def toDict(self):
        data = {
            'orderId': self._orderId,
            'symbol': self._symbol,
            'status': self._status,
            'timestamp': self._timestamp,
            'side': self._side,
            'price': self._price,
            'origQuantity': self._origQuantity
        }
        return data
