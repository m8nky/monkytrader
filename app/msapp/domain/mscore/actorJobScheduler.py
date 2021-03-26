import logging
from pytz import utc
from apscheduler.schedulers.background import BackgroundScheduler

class ActorJobScheduler:
    actor = None

    @staticmethod
    def executeTask():
        ActorJobScheduler.actor.executeTask()

    def __init__(self, actor):
        self.logger = logging.getLogger(__name__)
        assert actor is not None
        ActorJobScheduler.actor = actor
        self.scheduler = BackgroundScheduler(timezone=utc)
        self.scheduler.add_job(ActorJobScheduler.executeTask, 'interval', seconds=1)
        self.logger.debug('Background job scheduler initialized')

    def registerAppJobInterval(self, name: str, runnerCallback, **timeargs):
        args = [ arg in ['minutes', 'seconds'] for arg in timeargs.keys() ]
        assert False not in args and len(args) >= 1, "**timeargs does not contain valid time information."
        self.scheduler.add_job(runnerCallback, 'interval', id=name, replace_existing=True, **timeargs)
        self.logger.info("New app-level background job added '" + name + "'.")

    def run(self, paused=False):
        self.scheduler.start(paused=paused)
        self.logger.debug('Background job scheduler started')
