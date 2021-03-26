from .cryptoTradingService import CryptoTradingService

def bootstrap():
    import logging
    import msapp.domain.mscore
    cts = CryptoTradingService()
    logging.getLogger(__name__).debug("Attaching CryptoTradingService to actorExecutor.")
    msapp.domain.mscore.actor._actorExecutor._service = cts
    cts.bootstrap(msapp.domain.mscore.actor)
