import logging
import simplejson as json

from msapp.domain.repository import Position

class PositionStore:
    def __init__(self, storage):
        self._l = logging.getLogger(__name__)
        self._storage = storage

    def save(self, position: Position):
        data = position.toDict()
        self._storage.hashSet('position', str(position.id()), json.dumps(data))

    def load(self, positionId):
        data = self._storage.hashGet('position', str(positionId))
        if data is None:
            self._l.error(f"Requested positionId '{positionId}' not found in datastore.")
            return None
        return Position.fromDict(json.loads(data, use_decimal=True))

    def loadAllPositions(self):
        data = self._storage.hashValues('position')
        if data is None:
            self._l.error(f"Requested name 'position' not found in datastore.")
            return None
        return [ Position.fromDict(json.loads(e, use_decimal=True)) for e in data ]
