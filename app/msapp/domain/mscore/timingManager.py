import logging
import time
from multiprocessing import Manager

class TimingManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._manager = Manager()
        self._mutex = self._manager.Lock()
        self._average = self._manager.dict({
            'count': 0,
            'avg': None
        })
        self._start = 0

    def beginSequence(self):
        self._start = time.time()

    def endSequence(self):
        duration = -1
        if self._start:
            duration = time.time() - self._start
            self._applyCumulativeAverage(duration)
        else:
            self.logger.warn("Task timer missing start value.")
        self._start = 0
        return duration

    def averageExecutionDuration(self):
        self._mutex.acquire()
        try:
            return self._average.get('avg')
        except Exception:
            raise
        finally:
            self._mutex.release()

    def _applyCumulativeAverage(self, duration):
        self._mutex.acquire()
        try:
            avg = self._average.get('avg')
            cnt = self._average.get('count')
            if cnt == 0:
                # avg(1)
                avg = duration
            else:
                # avg(n) : n > 1
                avg = ((avg * cnt) + duration) / (cnt + 1)
            cnt += 1
            self._average.update({'avg': avg, 'count': cnt})
        except Exception:
            raise
        finally:
            self._mutex.release()
