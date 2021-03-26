import logging
import re
import ulid

import msapp.datamapper
import msapp.gateway
from msapp.domain.mscore import Task
from msapp.domain.service.tradingstrategy import LadderTradingStrategy

class CryptoTradingService:
    _taskActor = None

    def __init__(self):
        self._l = logging.getLogger(__name__)
        self._runningStrategies = []

    def bootstrap(self, taskActor=None):
        # Bootstrap application.
        if not CryptoTradingService._taskActor:
            assert taskActor is not None, "FATAL: Missing initialization of _taskActor"
            CryptoTradingService._taskActor = taskActor
        # Initializing LadderTradingStrategy for BTCUSDT on binance.
        conf = msapp.datamapper.tradingconfig.loadByName("binance_BTCUSDT_ladder")
        assert conf, "Missing config for 'binance_BTCUSDT_ladder'. Please prepare trading config before continuing."
        assert conf['strategy'] in ["LadderTradingStrategy"], "FATAL: Missing strategy 'LadderTradingStrategy'."
        symbol = conf['symbol']
        # Start trade stream for 'symbol' on binance.
        msapp.gateway.binanceAPI.startTradeStream(symbol)
        positions = []
        for p in conf['positions']:
            self._l.info(p)
            po = msapp.datamapper.positionstore.load(p)
            assert po is not None, f"Missing position '{p}' in datastore."
            positions.append(po)
        assert len(positions) > 0, "ERROR: Trying to initialize LadderTradingStrategy without positions."
        self._l.info(f"Initialize '{conf['strategy']}' ({symbol}) with {len(positions)} positions.")
        strategy = LadderTradingStrategy(symbol, positions)
        assert strategy.bootstrap(), "FATAL: Strategy bootstrap initialization failed."
        self._runningStrategies.append(strategy)
        # Start main loop.
        task = Task(id="TASK_LOOP_TRADING_SERVICE", data={})
        CryptoTradingService._taskActor.postTask(task)

    def process(self, task: Task):
        if task.status() in [ Task.STATUS_FAILED, Task.STATUS_SUCCESS ]:
            return
        if task.status() == Task.STATUS_NEW:
            task.setStatus(Task.STATUS_PROCESSING)
            if task.id() != 'TASK_LOOP_TRADING_SERVICE':
                task.save()
        res = self._dispatchTask(task)
        return res

    def _dispatchTask(self, task: Task):
        if re.match(r'TASK_LOOP_TRADING_SERVICE', task.id()) is not None:
            self._l.debug("=> Task '" + task.id() + "'.")
            res = False
            for strategy in self._runningStrategies:
                res = strategy.step()
                if not res:
                    task.setStatus(Task.STATUS_FAILED)
                    self._l.error("<= (" + task.status() + ") Task '" + task.id() + "'.")
                    self._runningStrategies.remove(strategy)
                    # Notify Telegram that trading failed and strategy has been stopped!
                    msapp.gateway.telegramAPI.notify(f"Trading failed, strategy has been stopped!")
                    continue
                task.setStatus(Task.STATUS_SUCCESS)
            # Reschedule task to end of queue to create a loop
            loopTask = Task(id="TASK_LOOP_TRADING_SERVICE_" + ulid.ulid(), data={})
            CryptoTradingService._taskActor.postTask(loopTask)
            if not res:
                return False
            self._l.debug("<= Task '" + task.id() + "'.")
            return True
