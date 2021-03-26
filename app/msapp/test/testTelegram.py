import logging
import unittest
from nose.plugins.attrib import attr

from msapp.gateway.telegram import Telegram

@attr('telegram')
class TestTelegram(unittest.TestCase):
    def __init__(self, methodName='runTest'):
        unittest.TestCase.__init__(self, methodName)
        self._l = logging.getLogger(__name__)

    @attr('telegram_testmessage')
    def test_testmessage(self):
        notifier = Telegram("monkytrader")
        self.assertTrue(notifier.enabled(), "Missing Telegram chat and key.")
        self.assertTrue(notifier.notify("Hello World!"), "Sending test message failed.")

    @attr('telegram_notifyonce')
    def test_notifyonce(self):
        notifier = Telegram("monkytrader")
        self.assertTrue(notifier.enabled(), "Missing Telegram chat and key.")
        self.assertTrue(notifier.notifyOnce("h", "Hello World!"), "Sending test message failed.")
        self.assertTrue(notifier.notifyOnce("h", "Hello World!"), "Sending test message failed.")
