#!/usr/bin/env python3
"""A wrapper for the FtRestClient for use in the FTUI"""

import sys
from time import sleep

import json, random, sys, os, re, argparse, traceback, statistics
from datetime import datetime, timezone, timedelta
from time import sleep
from itertools import cycle
import logging
import requests

import pandas as pd
import numpy as np

from urllib.request import urlopen

import rest_client as ftrc

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("ftui_client")

class FTUIClient():

    def __init__(self, name, url, port, username, password, config_path=None):
        self.name = name
        self.url = url
        self.port = port
        self.username = username
        self.password = password
        self.config_path = config_path
        self.rest_client = None

        self.prev_closed_trade_count = 0
        self.all_closed_trades = []

        self.setup_client()

    def setup_client(self):
        if self.url is None and self.port is None:
            config = ftrc.load_config(self.config_path)
            self.url = config.get('api_server', {}).get('listen_ip_address', '127.0.0.1')
            self.port = config.get('api_server', {}).get('listen_port', '8080')
            
            if self.username is None and self.password is None:
                self.username = config.get('api_server', {}).get('username')
                self.password = config.get('api_server', {}).get('password')
        else:
            if self.config_path is not None:
                config = ftrc.load_config(self.config_path)
                
                if self.username is None and self.password is None:
                    self.username = config.get('api_server', {}).get('username')
                    self.password = config.get('api_server', {}).get('password')

        if self.name is None:
            self.name = f"{self.url}:{self.port}"

        server_url = f"http://{self.url}:{self.port}"

        client = ftrc.FtRestClient(server_url, self.username, self.password)
        
        if client is not None:
            c = client.version()
            if c is not None:
                if "detail" in c.keys() and (c["detail"] == 'Unauthorized'):
                    raise Exception(f"Could not connect to bot [{self.url}:{self.port}]: Unauthorised")
            else:
                raise Exception(f"Could not connect to bot [{self.url}:{self.port}]: Check that http://{self.url}:{self.port}/api/v1/ping works in a browser, and check any firewall settings.")
        else:
            raise Exception(f"Could not connect to bot [{self.url}:{self.port}]: Error creating client")

        self.rest_client = client
        current_config = self.get_client_config()
        bot_state = current_config['state']
        runmode = current_config['runmode']
        strategy = current_config['strategy']

        print(f"Setting up {self.name} version {c['version']} at {server_url}: {strategy} {bot_state} {runmode}")
        sleep(1)
    
    def get_client_config(self):
        current_config = self.rest_client.show_config()

        # bot_state = current_config['state']
        # runmode = current_config['runmode']
        # strategy = current_config['strategy']
        # stoploss = abs(current_config['stoploss']) * 100
        # max_open_trades = current_config['max_open_trades']
        # stake_amount = current_config['stake_amount']

        return current_config

    def get_all_closed_trades(self) -> dict:
        cl = self.rest_client
        ps = cl.profit()

        if ps is not None:
            num_all_closed_trades = int(ps['closed_trade_count'])

            if num_all_closed_trades != self.prev_closed_trade_count:
                m, r = divmod(int(num_all_closed_trades), 500)
                trades = []

                if m > 1:
                    ## get last 500
                    cltrades = cl.trades()
                    if cltrades is not None and 'trades' in cltrades:
                        clt = cltrades['trades']
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)

                    for i in range(1, m+1):
                        cltrades = cl.trades(offset=(500 * i))
                        if cltrades is not None and 'trades' in cltrades:
                            clt = cltrades['trades']
                            if clt is not None and len(clt) > 0:
                                trades.extend(clt)                        

                elif m == 1:
                    cltrades = cl.trades()
                    if cltrades is not None and 'trades' in cltrades:
                        clt = cltrades['trades']
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)                    

                    cltrades = cl.trades(offset=500)
                    if cltrades is not None and 'trades' in cltrades:
                        clt = cltrades['trades']
                        if clt is not None and len(clt) > 0:
                            trades.extend(clt)                    
                else:
                    cltrades = cl.trades()
                    if cltrades is not None and 'trades' in cltrades:
                        clt = cltrades['trades']
                        if clt is not None and len(clt) > 0:
                            trades = clt
                
                trades.reverse()
                self.all_closed_trades = trades
                self.prev_closed_trade_count = len(trades)

        return self.all_closed_trades

def main(args):
    if args.get("show"):
        sys.exit()

if __name__ == "__main__":
    main()
