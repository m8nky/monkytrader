import logging
from decimal import Decimal

import msapp.datamapper

class Trade:
    SIDE_BUY = 'BUY'
    SIDE_SELL = 'SELL'

    @staticmethod
    def fromDict(data: dict):
        o = Trade(data['tradeId'])
        o._orderId = data['orderId']
        o._symbol = data['symbol']
        o._timestamp = data['timestamp']
        o._side = data['side']
        o._price = data['price']
        o._quantity = data['quantity']
        o._quoteQuantity = data['quoteQuantity']
        o._commissionAmount = data['commissionAmount']
        o._commissionAsset = data['commissionAsset']
        return o

    def __init__(self, tradeId: int,
                 orderId: int = None,
                 symbol: str = None,
                 timestamp: int = None,
                 side: str = None,
                 price: Decimal = None,
                 quantity: Decimal = None,
                 quoteQuantity: Decimal = None,
                 commissionAmount: Decimal = None,
                 commissionAsset: str = None):
        logging.getLogger(__name__)
        self._tradeId = tradeId
        self._orderId = orderId
        self._symbol = symbol
        self._timestamp = timestamp
        self._side = side
        self._price = price
        self._quantity = quantity
        self._quoteQuantity = quoteQuantity
        self._commissionAmount = commissionAmount
        self._commissionAsset = commissionAsset

    def save(self):
        msapp.datamapper.tradestore.save(self)

    def id(self):
        return self._tradeId

    def orderId(self):
        return self._orderId

    def side(self):
        return self._side

    def quantity(self):
        return self._quantity

    def quoteQuantity(self):
        return self._quoteQuantity

    def commissionAmount(self):
        return self._commissionAmount

    def commissionAsset(self):
        return self._commissionAsset

    def toDict(self):
        data = {
            'tradeId': self._tradeId,
            'orderId': self._orderId,
            'symbol': self._symbol,
            'timestamp': self._timestamp,
            'side': self._side,
            'price': self._price,
            'quantity': self._quantity,
            'quoteQuantity': self._quoteQuantity,
            'commissionAmount': self._commissionAmount,
            'commissionAsset': self._commissionAsset
        }
        return data
