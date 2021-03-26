import redis
import logging

class RedisDB:
    HOST = 'redis'
    PORT = 6379
    ENCODING = 'utf-8'

    def __init__(self):
        self._l = logging.getLogger(__name__)
        self._db = redis.Redis(host=RedisDB.HOST, port=RedisDB.PORT, encoding=RedisDB.ENCODING)

    def set(self, key: str, value: str):
        self._db.set(key, value)

    def get(self, key: str):
        return self._db.get(key)

    def hashSet(self, name: str, key: str, value: str):
        self._db.hset(name, key, value)

    def hashGet(self, name: str, key: str):
        return self._db.hget(name, key)

    def hashKeys(self, name: str):
        return self._db.hkeys(name)

    def hashValues(self, name: str):
        return self._db.hvals(name)

    def hashGetAll(self, name: str):
        data = self._db.hgetall(name)
        return [ (key, value) for i1, key in enumerate(data[::2]) for i2, value in enumerate(data[1::2]) if i1 == i2 ]
