import logging
import requests
import re
import time

from msapp import config

class Telegram:
    API_URL = 'https://api.telegram.org/bot{key}/sendMessage'

    def __init__(self, context: str):
        self._l = logging.getLogger(__name__)
        self._chatId = None
        self._key = None
        # Initialize message config.
        telegramConfig = config.c['telegram'][context]
        if not telegramConfig['chat-id'] or not telegramConfig['key']:
            self._l.warning("Missing TELEGRAM config. Notifications disabled.")
            return
        self._chatId = telegramConfig['chat-id']
        self._key = telegramConfig['key']
        self._notifyOnce = {}

    def enabled(self):
        return type(self._chatId) is str and len(self._chatId) > 0 and type(self._key) is str and len(self._key) > 0

    def notify(self, msg: str, timeout: int = 10):
        if not self.enabled():
            self._l.warning(f"Trying to issue Telegram message on an uninitialized Telegram gateway: {msg}")
            return False
        try:
            url = re.sub(r'{key}', self._key, Telegram.API_URL)
            payload = {
                'chat_id': self._chatId,
                'disable_web_page_preview': 1,
                'text': msg
            }
            res = requests.get(url, params=payload)
            assert res.status_code == requests.codes.ok, "ERROR: Telegram failed to send message."
        except Exception:
            self._l.exception(f"Send Telegram message failed: {msg}")
            return False
        return True

    def notifyOnce(self, key: str, msg: str, timeout: int = 10):
        if key in self._notifyOnce:
            return True
        res = self.notify(msg, timeout)
        if not res:
            return res
        self._notifyOnce[key] = int(time.time())
        return res
