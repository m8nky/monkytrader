import logging
import ulid
import simplejson as json

import msapp.datamapper

class Task:
    STATUS_NEW = "NEW"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_FAILED = "FAILED"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_POSTPONED = "POSTPONED"
    STATUS_UNKNOWN = "UNKNOWN"

    @staticmethod
    def createFromJson(jdata):
        data = json.loads(jdata, use_decimal=True) if type(jdata) is str else jdata
        assert 'id' in data and 'status' in data and 'status_hook' in data and 'data' in data, "ERROR: Creating task from JSON, missing data."
        task = Task(None)
        task._id = data['id']
        task._status = data['status']
        task._status_hook = data['status_hook']
        task._data = data['data']
        return task

    def __init__(self, data, id=None, status_hook=None):
        self._l = logging.getLogger(__name__)
        # New task created.
        self._id = ulid.ulid().lower() if id is None else id
        self._status = Task.STATUS_NEW
        self._status_hook = status_hook
        self._data = data

    def id(self):
        return self._id

    def data(self):
        return self._data

    def status(self):
        return self._status

    def setStatus(self, status: str):
        self._status = status
        return self

    def save(self):
        if msapp.datamapper.taskstore is None:
            self._l.debug("Task has no persistence in this context - '" + self.id() + "' not saved.")
            return False
        try:
            msapp.datamapper.taskstore.save(self)
        except Exception:
            self._l.exception("ERROR: Saving task '" + self.id() + "' failed.")
            return False
        return True

    def sendStatusReport(self):
        raise NotImplementedError()

    def toDict(self):
        data = {
            'id': self._id,
            'status': self._status,
            'status_hook': self._status_hook,
            'data': self._data
        }
        return data

    def toJson(self):
        return json.dumps(self.toDict(), ensure_ascii=False, indent=2)
