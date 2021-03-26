import logging
import datetime
from multiprocessing import Manager

from .tTLtool import TTLtool

class TaskQueue:
    TASK_STATUS_QUEUED = "QUEUED"
    TASK_STATUS_IN_PROGRESS = "IN_PROGRESS"

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Shared objects between gunicorn workers and task executor.
        self.manager = Manager()
        self.mutex = self.manager.Lock()
        self.queuedTasks = self.manager.list()   # multitasking and thread-safe list of tasks
        self.runningTasks = self.manager.list()  # multitasking and thread-safe list of tasks

    def add(self, task):
        self.mutex.acquire()
        try:
            self.queuedTasks.append(task)
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()

    def addStarted(self, task):
        self.mutex.acquire()
        try:
            self.runningTasks.append(task)
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()

    def startNext(self):
        self.mutex.acquire()
        try:
            for i, task in enumerate(self.queuedTasks):
                not_before = task.get('JQ_not_before', None)
                if not_before and not TTLtool.isExpirationtimeIsoExpired(not_before):
                    continue
                self.queuedTasks.pop(i)
                task.pop('JQ_not_before', None)
                self.runningTasks.append(task)
                return task
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()
        return None

    def finalize(self, job_id, rescheduleDeferralTime=None):
        self.mutex.acquire()
        try:
            # Match job_id to find task to drop.
            for i, task in enumerate(self.runningTasks):
                if task['id'] == job_id:
                    self.runningTasks.pop(i)
                    if rescheduleDeferralTime:
                        # Instead of dropping the Job, reschedule it.
                        task['JQ_not_before'] = TTLtool.calculateExpirationTimeIso(datetime.datetime.utcnow().isoformat(), rescheduleDeferralTime)
                        # Insert in front of the queue, so it gets rescheduled soon.
                        self.queuedTasks.insert(0, task)
                    return
            raise Exception("Job '%s' not found in running tasks list.", job_id)
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()

    def inList(self, job_id):
        self.mutex.acquire()
        try:
            for task in self.runningTasks:
                if task['id'] == job_id:
                    return True
            for task in self.queuedTasks:
                if task['id'] == job_id:
                    return True
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()
        return False

    def list(self):
        tasklist = []
        self.mutex.acquire()
        try:
            for task in self.runningTasks:
                tasklist.append({
                    'Job': task['id'],
                    'Status': TaskQueue.TASK_STATUS_IN_PROGRESS
                })
            for task in self.queuedTasks:
                tasklist.append({
                    'Job': task['id'],
                    'Status': TaskQueue.TASK_STATUS_QUEUED
                })
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()
        return tasklist

    def flushQueued(self):
        nof = 0
        self.mutex.acquire()
        try:
            nof = len(self.queuedTasks)
            self.queuedTasks[:] = []
        except Exception:
            self.logger.exception("FATAL: Job queue broken, this is a bug, please investigate!")
            raise
        finally:
            self.mutex.release()
        return nof
