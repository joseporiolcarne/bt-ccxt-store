import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import time
from datetime import datetime, timedelta
import logging
from ccxt import binance

import backtrader as bt
from backtrader import Order

from ccxtbt import CCXTStore


class TestStrategy(bt.Strategy):

    def __init__(self):

        self.bought = False
        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buy_time = None
        self.sell_order = None

    def next(self):

        if self.live_data and not self.bought:
            # Buy
            # size x price should be >10 USDT at a minimum at Binance
            # make sure you use a price that is below the market price if you don't want to actually buy
            self.order = self.buy(size=2, exectype=Order.Market)
            # And immediately cancel the buy order
            # self.cancel(self.order)
            self.bought = True
            self.buy_time = datetime.now()
            print(f"Bought at {self.data.close[0]} at {self.buy_time}")

        # Check if 3 minutes have passed since the buy
        if self.bought and (datetime.now() - self.buy_time >= timedelta(minutes=3)):
            # Sell at market price
            if self.sell_order is None:
                self.sell_order = self.sell(size=0.1, exectype=Order.Market)
                print(f"Sold at {self.data.close[0]} at {datetime.now()}")

        for data in self.datas:
            print(
                "{} - {} | O: {} H: {} L: {} C: {} V:{}".format(
                    data.datetime.datetime(),
                    data._name,
                    data.open[0],
                    data.high[0],
                    data.low[0],
                    data.close[0],
                    data.volume[0],
                )
            )

    def notify_data(self, data, status, *args, **kwargs):
        dn = data._name
        dt = datetime.now()
        msg = "Data Status: {}, Order Status: {}".format(
            data._getstatusname(status), status
        )
        print(dt, dn, msg)
        if data._getstatusname(status) == "LIVE":
            self.live_data = True
        else:
            self.live_data = False


# absolute dir the script is in
script_dir = os.path.dirname(__file__)
abs_file_path = os.path.join(script_dir, "../params.json")
with open(abs_file_path, "r") as f:
    params = json.load(f)

cerebro = bt.Cerebro(quicknotify=True)

cerebro.broker.setcash(10.0)

# Add the strategy
cerebro.addstrategy(TestStrategy)

# Create our store
config = {
    "apiKey": params["binance"]["apikey"],
    "secret": params["binance"]["secret"],
    "enableRateLimit": True,
    "nonce": lambda: str(int(time.time() * 1000)),
    "options": {
        "defaultType": "future",  # spot, margin, future
    },
}

logging.basicConfig(level=logging.DEBUG)

# exchange = binance(
#     {
#         "apiKey": params["binance"]["apikey"],
#         "secret": params["binance"]["secret"],
#         "enableRateLimit": True,
#         "options": {
#             "defaultType": "future",  # spot, margin, future
#         },
#     }
# )

# exchange.set_sandbox_mode(True)

# exchange.load_markets()


# try:
#     balance = exchange.fetch_balance()
#     print(balance)
# except Exception as e:
#     logging.error("Error fetching balance: %s", e)

store = CCXTStore(
    exchange="binance",
    currency="BNB",
    config=config,
    retries=5,
    debug=False,
    sandbox=True,
)

# Get the broker and pass any kwargs if needed.
# ----------------------------------------------
# Broker mappings have been added since some exchanges expect different values
# to the defaults. Case in point, Kraken vs Bitmex. NOTE: Broker mappings are not
# required if the broker uses the same values as the defaults in CCXTBroker.
broker_mapping = {
    "order_types": {
        bt.Order.Market: "market",
        bt.Order.Limit: "limit",
        bt.Order.Stop: "stop-loss",  # stop-loss for kraken, stop for bitmex
        bt.Order.StopLimit: "stop limit",
    },
    "mappings": {
        "closed_order": {"key": "status", "value": "closed"},
        "canceled_order": {"key": "status", "value": "canceled"},
    },
}

broker = store.getbroker(broker_mapping=broker_mapping)
cerebro.setbroker(broker)


# Get our data
# Drop newest will prevent us from loading partial data from incomplete candles
hist_start_date = datetime.utcnow() - timedelta(minutes=50)
data = store.getdata(
    dataname="BNB/USDT",
    name="BNBUSDT",
    timeframe=bt.TimeFrame.Minutes,
    fromdate=hist_start_date,
    compression=1,
    ohlcv_limit=50,
    drop_newest=True,
)  # , historical=True)

# Add the feed
cerebro.adddata(data)

# Run the strategy
cerebro.run()
