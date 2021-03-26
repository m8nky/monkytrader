from decimal import Decimal
import simplejson as json
import redis

from msapp.datamapper import initDatastores
from msapp.domain.repository import Position

def createPositions():
    initDatastores()
    symbol = "BTCUSDT"
    quoteVolume = Decimal("30.0")  # 30 USDT per ladder.
    positions = [
        {
            'buyLimit': Decimal("6708.49"),
            'sellLimit': Decimal("6864.65")
        },
        {
            'buyLimit': Decimal("6864.65"),
            'sellLimit': Decimal("7121.08")
        },
        {
            'buyLimit': Decimal("7121.08"),
            'sellLimit': Decimal("7269.64")
        },
        {
            'buyLimit': Decimal("7269.64"),
            'sellLimit': Decimal("7336.64")
        },
        {
            'buyLimit': Decimal("7336.64"),
            'sellLimit': Decimal("7416.95")
        }
    ]
    positionIds = []
    for p in positions:
        pos = Position.createLongLadder(symbol=symbol, highSellLimit=p['sellLimit'], lowBuyLimit=p['buyLimit'], volume=Decimal('0.0'), quoteVolume=quoteVolume)
        pos.save()
        positionIds.append(pos.id())
    return positionIds

if __name__ == '__main__':
    posIds = createPositions()
    r = redis.Redis('redis')
    cryptoconf = {
        'strategy': "LadderTradingStrategy",
        'symbol': "BTCUSDT",
        'positions': posIds
    }
    r.set("binance_BTCUSDT_ladder", json.dumps(cryptoconf))
