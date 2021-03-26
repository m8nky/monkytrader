import logging
import datetime

from msapp import config
from .exceptions import LongTemporaryFailureException
from .taskQueue import TaskQueue
from .task import Task
from .timingManager import TimingManager

class Actor(object):
    def __init__(self, actorExecutor):
        self._l = logging.getLogger(__name__)
        self._taskQueue = TaskQueue()  # Multiprocessing and thread-safe task queue with status information
        self._actorExecutor = actorExecutor
        self._taskTiming = TimingManager()

    # Actor API services
    def status(self):
        STATUS_OK = 'OK'
        STATUS_DEGRADED = 'DEGRADED'
        # Test overall microservice status
        status = {}
        status['Service Name'] = self._actorExecutor.__class__.SERVICE_NAME
        status['Time'] = datetime.datetime.now().isoformat()
        status['Message'] = ''
        # Collect active and queued tasks information
        status['TasksInQueue'] = len(self._taskQueue.list())
        status['AvgTaskDuration'] = self._taskTiming.averageExecutionDuration()
        is_online = True
        # Overall health status of this microservice
        status['Status'] = STATUS_OK if is_online else STATUS_DEGRADED
        # Invoke act status for microservice specific status information.
        self._actorExecutor.status(status)
        return status

    def taskStatus(self, task_id: str):
        return self._taskQueue.inList(task_id)

    def postTask(self, task: Task):
        params = task.toDict()
        assert self._validateTaskParams(params)
        # Add task to task queue, if it does not already exist.
        if not self._taskQueue.inList(params['id']):
            self._taskQueue.add(params)
        return { 'id': params['id'] }

    # Actor main loop executor
    def executeTask(self):
        """
          Actor main loop task executor.
          1. Get next task from task queue, that is not deferred due to LongTemporaryFailure.
          2. Create task status context (default: FAILED) and inject status report hook, if any
             given.
          3. Pass task to the specific actor executor.
             - If the actor executor requests the task to be deferred for some time, reschedule
               the task (default: 15 minutes).
          4. If task is done or failed, report the task status via status report hook (to the
             director), and drop it.
        """
        # Execution started from scheduler. Grab next task from queued task list.
        task = self._taskQueue.startNext()
        if task:
            retryDeferralTime = None
            taskObj = None
            try:
                self._l.debug("Task execution: '" + task['id'] + "'")
                # Invoke actor executor for customized actor handling
                try:
                    taskObj = Task.createFromJson(task)
                    # Set execution entry sequence point for task duration measurement.
                    self._taskTiming.beginSequence()
                    self._actorExecutor.execute(taskObj)
                except LongTemporaryFailureException:
                    retryDeferralTime = config.c['actor']['ltf-deferral-time']
            except Exception:
                raise
            finally:
                # After job is done or failed, drop it. If retryDeferralTime is set, reschedule job for later execution.
                if retryDeferralTime:
                    self._l.info("Rescheduled task for '" + task['id'] + "' in " + str(int(retryDeferralTime / 60)) + " minutes.")
                else:
                    # Job is about to be closed. Send status report to hook endpoint (director).
                    self._l.debug("Closing task for '" + task['id'] + "' with status '" + (taskObj.status() if taskObj else Task.STATUS_UNKNOWN) + "'.")
                    # Feed task timing statistics.
                    if taskObj and taskObj.status() == Task.STATUS_SUCCESS:
                        # Consider only fully successful tasks for duration measurement.
                        duration = self._taskTiming.endSequence()
                        self._l.debug("Task duration for '" + task['id'] + "': " + str(duration) + " seconds - Cum Avg: " + str(self._taskTiming.averageExecutionDuration()) + " seconds")
                self._taskQueue.finalize(task['id'], retryDeferralTime)

    # Force invalidation of all queued tasks.
    def invalidateTaskQueue(self):
        nof = self._taskQueue.flushQueued()
        self._l.debug("Dropped " + str(nof) + " queued tasks.")

    # Internals
    def _validateTaskParams(self, params):
        if 'invalidation_time' not in params:
            params['invalidation_time'] = '0'
        resjid = 'id' in params and type(params['id']) is str and len(params['id']) > 0
        if not resjid:
            self._l.error("Invalid parameters, 'id' is missing.")
            return False
        resitime = 'invalidation_time' in params and type(params['invalidation_time']) is str and len(params['invalidation_time']) > 0
        if not resitime:
            self._l.error("Invalid parameters, 'invalidation_time' is missing: '%s'", params['id'])
            return False
        resstatus = 'status' in params and type(params['status']) is str and len(params['status']) > 0
        if not resstatus:
            self._l.error("Invalid parameters, 'status is missing: '%s'", params['id'])
            return False
        resdata = 'data' in params and type(params['data']) is dict
        if not resdata:
            self._l.error("Invalid parameters, 'data' is missing: '%s'", params['id'])
            return False
        resact = self._actorExecutor.validateTaskParams(params['id'], params['data'])
        return resact
