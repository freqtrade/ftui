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
from textual.widgets import Button, DataTable, Footer, Header, Static, Tree
from textual.widgets.tree import TreeNode

import rest_client as ftrc
import ftui_client as ftuic

uniqclients = {}
client_dict = {}

all_closed_trades = {}

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

    def watch_show_clients(self, show_clients: bool) -> None:
        self.set_class(show_clients, "-show-clients")

    def action_toggle_clients(self) -> None:
        self.show_clients = (
            not self.show_clients
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Container(
                Tree("Clients", id="client-view"),
                id="left",
            ),
            Container(
                Horizontal(
                    id="top-right",
                ),
                Container(
                    id="bottom-right",
                ),
                id="right",
            ),
            id="parent-container"
        )
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        self.add_clients(tree.root, client_dict)
        tree.root.expand()
        tree.focus()

    @classmethod
    def add_clients(self, node: TreeNode, clients: dict) -> None:
        from rich.highlighter import ReprHighlighter
        highlighter = ReprHighlighter()

        def add_leaf_nodes(name: str, node: TreeNode, leaves: list) -> None:
            node._label = Text(f"{name}")
            for i in leaves:
                new_node = node.add("")
                new_node._allow_expand = False
                new_node._label = Text(i)

        def add_node(name: str, node: TreeNode, data: object) -> None:
            if isinstance(data, dict): # client_dict
                node._label = Text(f"{name}")
                for cl_name, ftui_client in data.items():
                    new_node = node.add("")
                    add_node(f"{cl_name}", new_node, ftui_client)
            elif isinstance(data, ftuic.FTUIClient): # actual client
                node._label = Text(f"{name}")
                new_node = node.add("")
                add_leaf_nodes(f"{data.name}", new_node, ["Summary", "Closed Trades", "Open Trades"])

        add_node("Clients", node, clients)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()

        if len(event.node.children) == 0:
            tr_cont = self.query_one("#top-right", Horizontal)
            br_cont = self.query_one("#bottom-right", Container)
            try:
                node_label = str(event.node.label)
                parent_name = str(event.node.parent.parent.label)
                
                if node_label == "Summary":
                    self.build_client_summary(tr_cont, client_dict[parent_name])
                elif node_label == "Closed Trades":
                    self.build_closed_trade_summary(tr_cont, client_dict[parent_name])
                #elif node_label == "Open Trades":
                    # node_view.update(Text(node_label))

                self.sub_title = f"{parent_name} - {node_label}"
            except Exception as e:
                tr_cont.update(Traceback(theme="github-dark", width=None))
                self.sub_title = "ERROR"

    def replace_summary_table(self, container, data):
        for st in container.query("#summary-table"):
            st.remove()

        rows = iter(data)
        dt = DataTable(id="summary-table")
        try:
            dt.add_columns(*next(rows))
            dt.add_rows(rows)
        except Exception as e:
            raise e
        container.mount(dt)

    def build_closed_trade_summary(self, container, ftuic):
        row_data = [
            ("Pair", "Profit %", "Profit", "Dur.", "Entry", "Exit"),
        ]
        fmt = "%Y-%m-%d %H:%M:%S"

        trades = ftuic.get_all_closed_trades()
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

        self.replace_summary_table(container, row_data)

    def build_client_summary(self, container, ftuic):
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

        # client = client_info[0]
        self.replace_summary_table(container, row_data)


class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

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
                        ftui_client = ftuic.FTUIClient(name=botname, url=url, port=port, username=suser, password=spass, config_path=config)
                    else:
                        ftui_client = ftuic.FTUIClient(name=s['name'], url=s['ip'], port=s['port'], username=s['username'], password=s['password'])
                    client_dict[ftui_client.name] = ftui_client
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
                            ftui_client = ftuic.FTUIClient(name=botname, url=url, port=port, username=suser, password=spass, config_path=config)
                        else:
                            ftui_client = ftuic.FTUIClient(name=botname, url=url, port=port, username=suser, password=spass)
                        client_dict[ftui_client.name] = ftui_client
                    except Exception as e:
                        raise RuntimeError("Cannot create freqtrade client") from e
                else:
                    raise Exception("Cannot parse server option. Please use [name]user:pass@servername:port")
    elif config is not None:
        try:
            ftui_client = ftuic.FTUIClient(config_path=config)
            client_dict[ftui_client.name] = ftui_client
        except Exception as e:
            raise RuntimeError('Cannot create freqtrade client') from e

    if not client_dict:
        raise Exception("No valid clients specified in config or --servers option")
    
if __name__ == "__main__":
    setup()
    FreqText().run()