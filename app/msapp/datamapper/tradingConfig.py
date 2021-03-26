import logging
import simplejson as json

class TradingConfig:
    def __init__(self, storage):
        self._l = logging.getLogger(__name__)
        self._storage = storage

    def loadByName(self, name: str):
        self._l.debug(f"Fetching config '{name}' from datastore.")
        data = self._storage.get(name)
        if data is None:
            self._l.error(f"Requested trading config '{name}' not found in datastore.")
            return None
        return json.loads(data, use_decimal=True)
