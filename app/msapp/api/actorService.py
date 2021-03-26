import logging
import falcon

import msapp.datamapper

class ActorService(object):
    def __init__(self, serviceHandler):
        self._l = logging.getLogger(__name__)
        Dashboard(serviceHandler)
        PostTask(serviceHandler)

class Dashboard:
    SERVICE = '/'

    def __init__(self, serviceHandler):
        self._l = logging.getLogger(__name__)
        serviceHandler.add_route(self.__class__.SERVICE, self)

    def on_head(self, req, resp):
        self._l.debug("HEAD " + self.__class__.SERVICE)
        resp.status = falcon.HTTP_OK

    def on_get(self, req, resp):
        self._l.debug("GET " + self.__class__.SERVICE)
        try:
            positions = msapp.datamapper.positionstore.loadAllPositions()
            positionsFull = [ p.toDictWithFullOrders() for p in positions ]
            trades = msapp.datamapper.tradestore.loadAllTrades()
            tradesFull = [ t.toDict() for t in trades ]
            req.context['result'] = { 'status': 'ok', 'positions': positionsFull, 'trades': tradesFull }
            resp.status = falcon.HTTP_OK
        except Exception:
            self._l.exception("Getting dashboard data failed.")
            req.context['result'] = {'status': 'failed'}
            resp.status = falcon.HTTP_500

class PostTask:
    SERVICE = '/api'

    def __init__(self, serviceHandler):
        self._l = logging.getLogger(__name__)
        serviceHandler.add_route(self.__class__.SERVICE, self)

    '''
      Deactivated API, currently not needed in this app-microservice.
    def on_post(self, req, resp):
        self._l.debug("POST " + self.__class__.SERVICE)
        data = req.context['doc']
        self._l.info("Data: " + json.dumps(data, indent=2))
        from msapp.domain.service import InboxService
        try:
            inbox = InboxService()
            id = inbox.newTask(data)
            self._l.info("Task queued for further processing.")
            req.context['result'] = {'status': 'ok', 'id': id}
            resp.status = falcon.HTTP_OK
        except Exception:
            self._l.exception("Queuing task failed.")
            req.context['result'] = {'status': 'failed'}
            resp.status = falcon.HTTP_500
    '''
