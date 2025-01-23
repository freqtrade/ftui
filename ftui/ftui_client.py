#!/usr/bin/env python3
"""A wrapper for the FtRestClient for use in the FTUI"""

import logging
import sys
from time import sleep
from typing import Optional

import freqtrade_client.ft_rest_client as ftrc
import numpy as np
import pandas as pd
from freqtrade_client.ft_client import load_config

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ftui_client")


class FTUIClient:
    def __init__(
        self,
        name: Optional[str] = None,
        url: Optional[str] = None,
        port: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        *,
        config_path=None,
        pool_connections=20,
        pool_maxsize=10,
    ):
        self.name = name
        self.url = url
        self.port = port
        self.username = username
        self.password = password
        self.config_path = config_path
        self.rest_client = None
        self.config = None
        self.pool_connections = pool_connections
        self.pool_maxsize = pool_maxsize

        self.prev_closed_trade_count = 0
        self.all_closed_trades = []

        self.setup_client()

    def setup_client(self):
        if self.url is None and self.port is None:
            config = load_config(self.config_path)
            self.url = config.get("api_server", {}).get("listen_ip_address", "127.0.0.1")
            self.port = config.get("api_server", {}).get("listen_port", "8080")

            if self.username is None and self.password is None:
                self.username = config.get("api_server", {}).get("username")
                self.password = config.get("api_server", {}).get("password")
        else:
            if self.config_path is not None:
                config = load_config(self.config_path)

                if self.username is None and self.password is None:
                    self.username = config.get("api_server", {}).get("username")
                    self.password = config.get("api_server", {}).get("password")

        #if self.name is None:
        #    self.name = f"{self.url}:{self.port}"

        server_url = f"http://{self.url}:{self.port}"

        client = ftrc.FtRestClient(server_url,
                                   self.username,
                                   self.password,
                                   pool_connections=self.pool_connections,
                                   pool_maxsize=self.pool_maxsize)

        if client is not None:
            c = client.version()
            if c is not None:
                if "detail" in c.keys() and (c["detail"] == "Unauthorized"):
                    raise Exception(
                        f"Could not connect to bot [{self.url}:{self.port}]: Unauthorised"
                    )
            else:
                raise Exception(
                    (
                        f"Could not connect to bot [{self.url}:{self.port}]: "
                        f"Check that http://{self.url}:{self.port}/api/v1/ping works in a browser "
                        f"and check any firewall settings."
                    )
                )
        else:
            raise Exception(
                f"Could not connect to bot [{self.url}:{self.port}]: Error creating client"
            )

        self.rest_client = client
        current_config = self.get_client_config()
        self.name = current_config.get(
            "bot_name",
            f"{self.url}:{self.port}"
        ) if self.name is None else self.name
        bot_state = current_config["state"]
        runmode = current_config["runmode"]
        strategy = current_config["strategy"]
        timeframe = current_config["timeframe"]

        self.config = current_config

        print(
            (
                f"Setting up {self.name} version {c['version']} at {server_url}: "
                f"{strategy} {bot_state} {runmode} {timeframe}"
            )
        )
        sleep(0.1)

    def get_client_config(self):
        if self.config is None:
            self.config = self.rest_client.show_config()

        # bot_state = current_config['state']
        # runmode = current_config['runmode']
        # strategy = current_config['strategy']
        # stoploss = abs(current_config['stoploss']) * 100
        # max_open_trades = current_config['max_open_trades']
        # stake_amount = current_config['stake_amount']

        # return current_config
        return self.config

    def get_pair_dataframe(self, pair, limit=200) -> pd.DataFrame:
        cl = self.rest_client
        candles = cl.pair_candles(
            pair, timeframe=self.get_client_config()["timeframe"], limit=limit
        )

        if candles is not None:
            cols = candles["columns"]
            data = candles["data"]

            if cols and data:
                df = pd.DataFrame(data, columns=cols)
                df.rename(
                    columns={"open": "Open", "close": "Close", "high": "High", "low": "Low"},
                    inplace=True,
                )
                return df

        return None

    def get_open_trade_count(self) -> dict:
        cl = self.rest_client
        counts = cl.count()
        if counts is not None and "current" in counts:
            return (counts["current"], counts["max"])

        return (0, 0)

    def get_all_closed_trades(self) -> list:
        cl = self.rest_client
        ps = cl.profit()

        if ps is not None:
            num_all_closed_trades = int(ps["closed_trade_count"])

            if num_all_closed_trades != self.prev_closed_trade_count:
                m, r = divmod(int(num_all_closed_trades), 500)
                trades = []

                if m > 1:
                    # get last 500
                    cltrades = cl.trades()
                    if cltrades is not None and "trades" in cltrades:
                        clt = cltrades["trades"]
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)

                    for i in range(1, m + 1):
                        cltrades = cl.trades(offset=(500 * i))
                        if cltrades is not None and "trades" in cltrades:
                            clt = cltrades["trades"]
                            if clt is not None and len(clt) > 0:
                                trades.extend(clt)

                elif m == 1:
                    cltrades = cl.trades()
                    if cltrades is not None and "trades" in cltrades:
                        clt = cltrades["trades"]
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)

                    cltrades = cl.trades(offset=500)
                    if cltrades is not None and "trades" in cltrades:
                        clt = cltrades["trades"]
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)
                else:
                    cltrades = cl.trades()
                    if cltrades is not None and "trades" in cltrades:
                        clt = cltrades["trades"]
                        if clt is not None and len(clt) > 0:
                            trades = clt

                trades.reverse()
                self.all_closed_trades = trades
                self.prev_closed_trade_count = len(trades)

        return self.all_closed_trades

    def get_open_trades(self) -> list:
        cl = self.rest_client
        ts = cl.status()

        trades = []
        if ts is not None:
            return ts
        return trades

    def get_total_profit(self) -> dict:
        cl = self.rest_client
        profit = cl.profit()
        return profit

    def get_daily_profit(self, days=1) -> dict:
        cl = self.rest_client
        profit = cl.daily(days=days)
        return profit

    def get_weekly_profit(self, weeks=1) -> dict:
        cl = self.rest_client
        profit = cl.weekly(weeks=weeks)
        return profit

    def get_monthly_profit(self, months=1) -> dict:
        cl = self.rest_client
        profit = cl.monthly(months=months)
        return profit

    def get_whitelist(self) -> list:
        cl = self.rest_client
        wl = cl.whitelist()
        if "whitelist" in wl and wl["whitelist"]:
            return wl["whitelist"]
        return []

    def get_performance(self) -> list:
        cl = self.rest_client
        perf = cl.performance()
        return perf

    def get_logs(self, limit=None) -> str:
        cl = self.rest_client

        if limit is not None:
            logjson = cl.logs(limit=limit)
        else:
            logjson = cl.logs()

        logstr = ""

        if logjson is not None and "logs" in logjson:
            logs = logjson["logs"]

            for logline in logs:
                logstr += f"{logline[0]} - {logline[2]} - {logline[3]} - {logline[4]}\n"

        return logstr

    def get_sys_info(self) -> list:
        cl = self.rest_client
        si = cl.sysinfo()
        return si

    def calc_risk(self):
        cl = self.rest_client
        bal = cl.balance()
        avail_bal = 0
        for b in bal["currencies"]:
            if b["currency"] == self.config["stake_currency"]:
                avail_bal = b["balance"]
                break

        if self.config["max_open_trades"] > 0:
            max_capit = 0
            if self.config["stake_amount"] != "unlimited":
                max_capit = float(self.config["stake_amount"] * self.config["max_open_trades"])
            else:
                max_capit = float(avail_bal / self.config["max_open_trades"])

            if max_capit > 0:
                risk_per_trade = ((max_capit / self.config["max_open_trades"]) / max_capit) * 100
                return -np.round(avail_bal * risk_per_trade / 100, 2)
            else:
                return 0
        else:
            return 0

    def get_trade_info(self, trade_id: int):
        cl = self.rest_client
        t = cl.trade(trade_id)
        return t


def main(args):
    if args.get("show"):
        sys.exit()


if __name__ == "__main__":
    main()
