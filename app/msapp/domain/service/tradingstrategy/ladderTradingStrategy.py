import logging
import time

import msapp.gateway
import msapp.datamapper
from msapp.domain import Trade
from msapp.domain.repository import Position
from msapp.domain.mscore import Task
from msapp.domain.mscore import TaskQueue

class LadderTradingStrategy:
    def __init__(self, symbol: str, positions: list):
        self._l = logging.getLogger(__name__)
        self._symbol = symbol
        self._positions = positions
        self._tradeEvents = None

    def bootstrap(self):
        self._l.info("LadderTradingStrategy bootstrap start...")
        # Check new trades and update orders and positions (if needed).
        if not self._updateTradesFromExchange():
            self._l.error("Fetching new trades from exchange.")
            return False
        # Invalidate orders that have been closed manually on exchange.
        if not self._invalidateClosedOrders():
            self._l.error("Invalidating closed orders failed.")
            return False
        # Place missing orders on exchange.
        if not self._placeMissingOrders():
            self._l.error("Placing missing trades failed. Abort trading.")
            return False
        # Register for trade updates.
        self._tradeEvents = msapp.gateway.binanceAPI.registerERqueue()
        assert self._tradeEvents is not None, "Registering trade listener failed."
        self._l.info("LadderTradingStrategy bootstrap finished :-)")
        return True

    def step(self):
        taskdata = self._tradeEvents.startNext()
        if taskdata:
            try:
                task = Task.createFromJson(taskdata)
                task.setStatus(Task.STATUS_PROCESSING)
                data = task.data()
                trade = Trade.fromDict(data)
                res = self._tradeEvent(trade)
                task.setStatus(Task.STATUS_SUCCESS if res is True else Task.STATUS_FAILED)
                self._tradeEvents.finalize(task.id())
            except Exception:
                self._l.exception("Failed processing trade.")
                return False
        try:
            self._placeMissingOrders()
        except Exception:
            self._l.exception("Failed placing missing orders.")
            return False
        return True

    def _updateTradesFromExchange(self):
        self._l.info("Check new trades and update orders and positions.")
        # Fetch open orders for this strategy.
        orders = { o.id(): o for p in self._positions for o in p.openOrders()  }
        # Evaluate if new trades occurred on exchange.
        trades = { t.id(): t for t in msapp.datamapper.tradestore.loadAllTrades() }
        # Fetch all trades starting with last known trade ID.
        tid = max(trades.keys()) if len(trades) > 0 else None
        exTrades = msapp.gateway.binanceAPI.getTrades(symbol=self._symbol, fromId=tid)
        # Skip trades not part of this strategy.
        exTrades = [ exTrade for exTrade in exTrades if exTrade.orderId() in orders ]
        # Update missing local trades.
        for exTrade in exTrades:
            if exTrade.id() not in trades:
                self._l.info(f"New trade detected '{exTrade.id()}'.")
                self._tradeEvent(exTrade)
        return True

    def _invalidateClosedOrders(self):
        self._l.info("Invalidate (manually) closed orders in positions.")
        # Fetch open orders for this strategy.
        orders = { o.id(): o for p in self._positions for o in p.openOrders()  }
        # Fetch all orders starting with first open order.
        oid = min(orders.keys()) if len(orders) > 0 else None
        if oid is None:
            return True
        exOrders = msapp.gateway.binanceAPI.getAllOrders(symbol=self._symbol, fromId=oid)
        # Skip orders not part of this strategy and skip open orders.
        exClosedOrders = [ exOrder for exOrder in exOrders if exOrder.id() in orders and exOrder.isClosed() ]
        # Compare exchange orders with local open orders, if status changed, .
        for exco in exClosedOrders:
            if exco.id() in orders:
                self._l.info(f"Found manually closed order '{exco.id()}' on exchange. Update local order.")
                order = orders[exco.id()]
                order.update(exco)
                order.save()
        return True

    def _tradeEvent(self, trade: Trade):
        # Update existing orders and positions.
        for position in self._positions:
            order = position.getOrder(trade.orderId())
            # Only process trades that belong to orders in this strategy object.
            if order is not None:
                _msg = f"New trade detected for position '{position.id()}' with order '{order.id()}': {trade.toDict()}"
                self._l.info(_msg)
                msapp.gateway.telegramAPI.notify(_msg)
                # Fetch updated order data from binance and update order data.
                bOrder = msapp.gateway.binanceAPI.getOrder(self._symbol, trade.orderId())
                assert bOrder is not None
                # Entering critical section.
                order.update(bOrder)
                position.updatePositionVolume(trade)
                order.save()
                position.save()
                trade.save()
        return True

    def _placeMissingOrders(self):
        # Get current symbol price.
        price = None
        while price is None:
            price = msapp.gateway.binanceAPI.getCurrentPrice(self._symbol)
            if price is None:
                self._l.warning(f"Price not found, waiting for exchange initialization to get current symbol price for '{self._symbol}'.")
                time.sleep(1)
        assert price, f"ERROR: Price not found for '{self._symbol}'. Wait for exchange initialization."
        # Orders placed on exchange.
        for position in self._positions:
            openOrders = position.openOrders()
            if len(openOrders) > 0:
                # Buy or sell order placed, nothing to do.
                continue
            # Fetch position parameters for placing orders.
            positionDef = position.position()
            assert positionDef['type'] == Position.TYPE_LONG_LADDER
            # Determine buy or sell order to be placed.
            volume = position.volume()
            if not volume.is_zero():
                # Place sell order, if price is below sellLimit.
                orderPrice = positionDef['high']['sellLimit']
                if price > orderPrice:
                    _msg = f"Current price {price} for '{self._symbol}' is above sell limit {orderPrice}. Avoid selling for more revenue."
                    self._l.warning(_msg)
                    # Notify user - intervention recommended.
                    _key = f"Current price for '{self._symbol}' is above sell limit {orderPrice}. Avoid selling for more revenue."
                    msapp.gateway.telegramAPI.notifyOnce(_key, _msg)
                    continue
                self._l.info(f"Try placing order for '{self._symbol}' - SELL '{volume}' for '{orderPrice}'.")
                if msapp.gateway.binanceAPI.isOrderPlaceable(self._symbol, "LIMIT_SELL", volume, orderPrice):
                    order = msapp.gateway.binanceAPI.placeLimitSellOrder(self._symbol, volume, orderPrice)
                    if order is None:
                        # Notify user - intervention required
                        _msg = f"Placing sell order failed for '{self._symbol}'."
                        self._l.error(_msg)
                        msapp.gateway.telegramAPI.notify(_msg)
                        raise Exception("STOP TRADING.")
                    position.assignOrder(order)
                    position.save()
                    order.save()
                    # For now, only single order is allowed per ladder.
                    continue
                else:
                    self._l.warning("Order can not be placed, maybe requested volume is out of accepted range.")
            quoteVolume = position.quoteVolume()
            if not quoteVolume.is_zero():
                # Place buy order, if price is above buyLimit.
                orderPrice = positionDef['low']['buyLimit']
                if price < orderPrice:
                    self._l.debug(f"Current price {price} for '{self._symbol}' is below buy limit {orderPrice}. Position '{position.id()}' not placed.")
                    continue
                # Calculate max buy volume.
                volume = position.calculateMaxBuyVolume(orderPrice)
                self._l.info(f"Try placing order for '{self._symbol}' - BUY '{volume}' at '{orderPrice}'.")
                if msapp.gateway.binanceAPI.isOrderPlaceable(self._symbol, "LIMIT_BUY", volume, orderPrice):
                    order = msapp.gateway.binanceAPI.placeLimitBuyOrder(self._symbol, volume, orderPrice)
                    if order is None:
                        # Notify user - intervention required.
                        _msg = f"Placing buy order failed for '{self._symbol}'."
                        self._l.error(_msg)
                        msapp.gateway.telegramAPI.notify(_msg)
                        raise Exception("STOP TRADING.")
                    position.assignOrder(order)
                    position.save()
                    order.save()
                else:
                    self._l.warning("Order can not be placed, maybe requested volume is out of accepted range.")
        return True
