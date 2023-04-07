#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
███████╗████████╗██╗   ██╗██╗
██╔════╝╚══██╔══╝██║   ██║██║
█████╗     ██║   ██║   ██║██║
██╔══╝     ██║   ██║   ██║██║
██║        ██║   ╚██████╔╝██║
╚═╝        ╚═╝    ╚═════╝ ╚═╝

Freqtrade Textual User Interface (FTUI)

Run with:

    python3 ftui.py -y yaml.file

"""

import sys
from time import sleep

import json, random, sys, os, re, argparse, traceback, statistics
from datetime import datetime, timezone, timedelta
from time import sleep
from itertools import cycle
import requests

import pandas as pd
import numpy as np

from urllib.request import urlopen

from rich.syntax import Syntax
from rich.text import Text
from rich.traceback import Traceback

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import var
from textual.widgets import Button, DataTable, Footer, Header, Static, TextLog, Tree, Markdown, TabbedContent, TabPane
from textual.widgets.tree import TreeNode

import rest_client as ftrc

uniqclients = {}
client_dict = {}

urlre = "^\[([a-zA-Z0-9]+)\]*([a-zA-Z0-9\-._~%!$&'()*+,;=]+)?:([ a-zA-Z0-9\-._~%!$&'()*+,;=]+)@?([a-z0-9\-._~%]+|\[[a-f0-9:.]+\]|\[v[a-f0-9][a-z0-9\-._~%!$&'()*+,;=:]+\]):([0-9]+)?"
dfmt = "%Y-%m-%d %H:%M:%S"

class FreqText(App):
    """
    Freqtrade text interface based on Textual.
    A spiritual successor to frogtrade9000.
    """

    CSS_PATH = "freqtext.css"
    BINDINGS = [
        ("c", "toggle_clients", "Toggle Client Browser"),
        ("q", "quit", "Quit"),
    ]

    show_clients = var(True)

    func_map = {
        "open-trades-tab":"update_open_trades_tab",
        "closed-trades-tab":"update_closed_trades_tab",
        "summary-trades-tab":"update_summary_trades_tab",
        "logs-tab":"update_logs_tab",
        "help-tab":"update_help_tab"
    }

    def debug(self, msg):
        debuglog = self.query_one("#debug-log")
        debuglog.write(msg)
        
    def tab_select_func(self, tab_id, bot_id):
        self.debug(f"Attempting select {tab_id} {bot_id}")
        if tab_id in self.func_map:
            getattr(self, self.func_map[tab_id])(tab_id, bot_id)

    def watch_show_clients(self, show_clients: bool) -> None:
        self.set_class(show_clients, "-show-clients")

    def action_toggle_clients(self) -> None:
        self.show_clients = (
            not self.show_clients
        )

    def action_show_tab(self, tab: str) -> None:
        self.get_child_by_type(TabbedContent).active = tab
        tree = self.query_one(Tree)
        bot_id = str(tree.cursor_node.label)
        self.update_tab(active_tab_id, bot_id)        

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="parent-container"):
            with Container(id="left"):
                yield Static("Dashboard")
                yield Tree("Clients", id="client-view")
            with Container(id="right"):
                with TabbedContent(initial="open-trades-tab"):
                    #with TabPane("Summary", id="all-bot-summary-tab")
                    #    yield DataTable(id="all-bot-summary-table")

                    with TabPane("Open Trades", id="open-trades-tab"):
                        yield DataTable(id="open-trades-table")

                    with TabPane("Closed Trades", id="closed-trades-tab"):
                        yield DataTable(id="closed-trades-table")
                    
                    with TabPane("Trade Summary", id="summary-trades-tab"):
                        yield DataTable(id="summary-trades-table")
                    
                    with TabPane("Logs", id="logs-tab"):
                        yield TextLog(id="log")

                    with TabPane("Help", id="help-tab"):
                        yield Markdown("#Hello", id="help")

                    with TabPane("Debug", id="debug-tab"):
                        yield TextLog(id="debug-log")

        yield Footer()

    @classmethod
    def add_clients(self, node: TreeNode, clients: dict) -> None:
        from rich.highlighter import ReprHighlighter
        highlighter = ReprHighlighter()

        def add_node(name: str, node: TreeNode, data: object) -> None:
            if isinstance(data, dict):
                node._label = Text(f"{name}")
                for cl_name, cl_info in data.items():
                    new_node = node.add("")
                    add_node(f"{cl_name}", new_node, cl_info)
            elif isinstance(data, list):
                node._label = Text(f"{name}")
                node._allow_expand = False

        add_node("Clients", node, clients)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()

        active_tab_id = self.query_one("#right").get_child_by_type(TabbedContent).active
        bot_id = str(event.node.label)
        
        self.update_tab(active_tab_id, bot_id)

    def update_tab(self, tab_id, bot_id):
        self.tab_select_func(tab_id, bot_id)

    def update_open_trades_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        return "foo"

    def update_closed_trades_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        data = self.build_closed_trade_summary(cl)
        tab = next(self.query(f"#{tab_id}").results(TabPane))
        self.replace_summary_table(data, tab)

    def update_summary_trades_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        return "foo"

    def update_logs_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = next(self.query(f"#{tab_id}").results(TabPane))
        tab.query_one("#log").write(f"Logging {tab_id} {bot_id}")

    def update_help_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        return "foo"

    def replace_summary_table(self, data, tab):
        dt = tab.get_child_by_type(DataTable)
        dt.clear(columns=True)

        rows = iter(data)
        try:
            dt.add_columns(*next(rows))
            dt.add_rows(rows)
        except Exception as e:
            raise e
        dt.refresh()

    def build_closed_trade_summary(self, client_info):
        row_data = [
            ("Pair", "Profit %", "Profit", "Dur.", "Entry", "Exit"),
        ]
        fmt = "%Y-%m-%d %H:%M:%S"
        client = client_info[0]
        trades = get_all_closed_trades(client)
        if trades is not None:
            for t in trades[:20]:
                otime = datetime.strptime(t['open_date'], fmt).astimezone(tz=timezone.utc)
                ctime = datetime.strptime(t['close_date'], fmt).astimezone(tz=timezone.utc)
                rpfta = round(float(t['profit_abs']), 2)

                row_data.append((
                    f"{t['pair']}",
                    f"[red]{t['profit_pct']}" if t['profit_pct'] <= 0 else f"[green]{t['profit_pct']}",
                    f"[red]{rpfta}" if rpfta <= 0 else f"[green]{rpfta}",
                    f"{str(ctime-otime).split('.')[0]}",
                    f"{t['enter_tag']}",
                    f"{t['exit_reason']}"
                ))

        return row_data

    def build_client_summary(self, container, client_info):    
        row_data = [
            ("lane", "swimmer", "country", "time"),
            # (4, "Joseph Schooling", "Singapore", 50.39),
            # (2, "Michael Phelps", "United States", 51.14),
            # (5, "Chad le Clos", "South Africa", 51.14),
            # (6, "László Cseh", "Hungary", 51.14),
            # (3, "Li Zhuhao", "China", 51.26),
            # (8, "Mehdy Metella", "France", 51.58),
            # (7, "Tom Shields", "United States", 51.73),
            # (1, "Aleksandr Sadovnikov", "Russia", 51.84),
            # (10, "Darren Burns", "Scotland", 51.84),
        ]

        client = client_info[0]
        self.replace_summary_table(container, row_data)

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        self.add_clients(tree.root, client_dict)
        tree.root.expand()
        tree.focus()

        self.query_one("#debug-log").write(Text("Hello"))
        

def setup_client(name=None, config_path=None, url=None, port=None, username=None, password=None):
    if url is None:
        config = ftrc.load_config(config_path)
        url = config.get('api_server', {}).get('listen_ip_address', '127.0.0.1')
        port = config.get('api_server', {}).get('listen_port', '8080')
        
        if username is None and password is None:
            username = config.get('api_server', {}).get('username')
            password = config.get('api_server', {}).get('password')
    else:
        if config_path is not None:
            config = ftrc.load_config(config_path)
            
            if username is None and password is None:
                username = config.get('api_server', {}).get('username')
                password = config.get('api_server', {}).get('password')

    if name is None:
        name = f"{url}:{port}"
    
    server_url = f"http://{url}:{port}"

    client = ftrc.FtRestClient(server_url, username, password)
    
    if client is not None:
        c = client.version()
        if c is not None:
            if "detail" in c.keys() and (c["detail"] == 'Unauthorized'):
                raise Exception(f"Could not connect to bot [{url}:{port}]: Unauthorised")
        else:
            raise Exception(f"Could not connect to bot [{url}:{port}]: Check that http://{url}:{port}/api/v1/ping works in a browser, and check any firewall settings.")
    else:
        raise Exception(f"Could not connect to bot [{url}:{port}]: Error creating client")

    current_config = client.show_config()
    bot_state = current_config['state']
    runmode = current_config['runmode']
    strategy = current_config['strategy']
    stoploss = abs(current_config['stoploss']) * 100
    max_open_trades = current_config['max_open_trades']
    stake_amount = current_config['stake_amount']
    
    stuff = [client, url, port, strategy, bot_state, runmode, stoploss, max_open_trades, stake_amount]
    
    print(f"Setting up {name} version {c['version']} at {server_url}: {strategy} {bot_state} {runmode}")
    sleep(1)
    
    if url not in uniqclients:
        uniqclients[url] = stuff
    
    return name, stuff

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def get_all_closed_trades(cl) -> dict:
    ps = cl.profit()
    
    if ps is not None:
        num_all_closed_trades = int(ps['closed_trade_count'])

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
    
    return trades

def setup():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debugging mode")
    parser.add_argument("-c", "--config", nargs='?', help="Config to parse")
    parser.add_argument("-y", "--yaml", nargs='?', help="Supply a YAML file instead of command line arguments.")
    
    parser.add_argument("--debug", nargs="?", help="Debug mode")
    
    args = parser.parse_args()
    
    # client_dict = {}
    
    config = args.config

    print(__doc__)
    
    if args.yaml is not None:
        import yaml
        with open(args.yaml, 'r') as yamlfile:
            args = dotdict(yaml.safe_load(yamlfile))
            args.yaml = True
    
    if "header_size" in args and args.header_size is not None:
        header_size = args.header_size
    else:
        header_size = 3
    
    if "side_panel_minimum_size" in args and args.side_panel_minimum_size is not None:
        side_panel_minimum_size = args.side_panel_minimum_size
    else:
        side_panel_minimum_size = 114
    
    if "num_days_daily" in args and args.num_days_daily is not None:
        num_days_daily = args.num_days_daily
    else:
        num_days_daily = 5

    if "num_closed_trades" in args and args.num_closed_trades is not None:
        num_closed_trades = args.num_closed_trades
    else:
        num_closed_trades = 2
    
    stake_coin = "USDT"
    if args.stake_coin is not None:
        stake_coin = args.stake_coin

    informative_coin = "BTC"
    if args.informative_coin is not None:
        informative_coin = args.informative_coin

    informative_pair = f"{informative_coin}/{stake_coin}"
    # chart_config['current_pair'] = informative_pair

    if args.servers is not None:
        if args.yaml:
            indicators = args.indicators
            
            for s in args.servers:
                try:
                    if config is not None:
                        name, client = setup_client(name=botname, url=url, port=port, username=suser, password=spass, config_path=config)
                    else:
                        name, client = setup_client(name=s['name'], url=s['ip'], port=s['port'], username=s['username'], password=s['password'])
                    client_dict[name] = client
                except Exception as e:
                    raise RuntimeError('Cannot create freqtrade client') from e
        else:
            slist = args.servers.split(",")
            for s in slist:
                m = re.match(urlre, s)
                if m:
                    botname = m.group(1)
                    suser = m.group(2)
                    spass = m.group(3)
                    url = m.group(4)
                    port = m.group(5)

                    if url is None or port is None:
                        raise Exception("Cannot get URL and port from server option. Please use [name]user:pass@servername:port")

                    try:
                        if config is not None:
                            name, client = setup_client(name=botname, url=url, port=port, username=suser, password=spass, config_path=config)
                        else:
                            name, client = setup_client(name=botname, url=url, port=port, username=suser, password=spass)
                        client_dict[name] = client
                    except Exception as e:
                        raise RuntimeError("Cannot create freqtrade client") from e
                else:
                    raise Exception("Cannot parse server option. Please use [name]user:pass@servername:port")
    elif config is not None:
        try:
            name, client = setup_client(config_path=config)
            client_dict[name] = client
        except Exception as e:
            raise RuntimeError('Cannot create freqtrade client') from e

    if not client_dict:
        raise Exception("No valid clients specified in config or --servers option")
    
if __name__ == "__main__":
    setup()
    FreqText().run()