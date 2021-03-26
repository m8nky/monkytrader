import datetime

class TTLtool:
    @staticmethod
    def calculateExpirationTimeIso(basetimeIso, initialTTL):
        basetime = datetime.datetime.strptime(basetimeIso.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        return (basetime + datetime.timedelta(seconds=initialTTL)).isoformat()

    @staticmethod
    def isExpirationtimeIsoExpired(expirationtimeIso):
        current_time = datetime.datetime.utcnow()
        expiration_time = datetime.datetime.strptime(expirationtimeIso.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        return current_time > expiration_time
