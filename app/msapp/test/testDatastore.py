import logging
import unittest
from nose.plugins.attrib import attr

from msapp.domain.repository import Position
from msapp.domain import Order
from msapp.domain import Trade
from msapp.datamapper import initDatastores
import msapp.datamapper

@attr('datastore')
class TestDatastore(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self._l = logging.getLogger(__name__)
        initDatastores()

    @attr('datastore_orderstore')
    def test_orderstore(self):
        o = Order("_testDatastore_1")
        msapp.datamapper.orderstore.save(o)
        on = msapp.datamapper.orderstore.load(o.id())
        self.assertDictEqual(o.toDict(), on.toDict(), "Orderstore data corrupted.")

    @attr('datastore_tradestore')
    def test_tradestore(self):
        o = Trade("_testDatastore_1")
        msapp.datamapper.tradestore.save(o)
        on = msapp.datamapper.tradestore.load(o.id())
        self.assertDictEqual(o.toDict(), on.toDict(), "Tradestore data corrupted.")

    @attr('datastore_position')
    def test_positionstore(self):
        o = Position("_testDatastore_1")
        msapp.datamapper.positionstore.save(o)
        on = msapp.datamapper.positionstore.load(o.id())
        self.assertDictEqual(o.toDict(), on.toDict(), "Positionstore data corrupted.")
