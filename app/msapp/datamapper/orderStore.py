import logging
import simplejson as json

from msapp.domain import Order

class OrderStore:
    def __init__(self, storage):
        self._l = logging.getLogger(__name__)
        self._storage = storage

    def save(self, order: Order):
        data = order.toDict()
        self._storage.hashSet('order', str(order.id()), json.dumps(data))

    def load(self, orderId):
        data = self._storage.hashGet('order', str(orderId))
        if data is None:
            self._l.error(f"Requested orderId '{orderId}' not found in datastore.")
            return None
        return Order.fromDict(json.loads(data, use_decimal=True))

    def loadAllOrders(self):
        data = self._storage.hashValues('order')
        if data is None:
            self._l.error(f"Requested name 'order' not found in datastore.")
            return None
        return [ Order.fromDict(json.loads(e, use_decimal=True)) for e in data ]
