import logging

from .tTLtool import TTLtool
from .task import Task

class ActorExecutor:
    SERVICE_NAME = "monkytrader"

    def __init__(self):
        self._l = logging.getLogger(__name__)
        self._service = None

    def status(self, status: dict):
        """
          Add some status fields, specific to this microservice, to give a clue about self-fitnes.

          This method is called after gathering the base actor status. So changing existing status
          fields will overwrite the response.
        """
        pass

    def validateTaskParams(self, task_id: str, params: dict):
        """
          This routine checks the mandatory fields of the job requests, if they are valid. Reason is,
          the endpoint can decline an invalid request, instead of queuing it and log an error later,
          which hardens the request API.
        """
        res = True
        return res

    def execute(self, task: Task):
        assert self._service, "FATAL: Actor service not initialized."
        result = {'status': Task.STATUS_UNKNOWN }
        self._service.process(task)
        result = {'status': task.status()}
        return result

    def _isExpired(self, invalidation_time: str):
        if TTLtool.isExpirationtimeIsoExpired(invalidation_time):
            self._l.warn("Task expired, but spider has not finished successfully. Dropping task!")
            return True
        return False
