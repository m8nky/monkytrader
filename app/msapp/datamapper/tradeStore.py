import logging
import simplejson as json

from msapp.domain import Trade

class TradeStore:
    def __init__(self, storage):
        self._l = logging.getLogger(__name__)
        self._storage = storage

    def save(self, trade: Trade):
        data = trade.toDict()
        self._storage.hashSet('trade', str(trade.id()), json.dumps(data))

    def load(self, tradeId):
        data = self._storage.hashGet('trade', str(tradeId))
        if data is None:
            self._l.error(f"Requested tradeId '{tradeId}' not found in datastore.")
            return None
        return Trade.fromDict(json.loads(data, use_decimal=True))

    def loadAllTrades(self):
        data = self._storage.hashValues('trade')
        if data is None:
            self._l.error(f"Requested name 'trade' not found in datastore.")
            return None
        return [ Trade.fromDict(json.loads(e, use_decimal=True)) for e in data ]
