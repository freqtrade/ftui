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

import asyncio, sys
from time import sleep

import json, random, sys, os, re, argparse, traceback, statistics
from datetime import datetime, timezone, timedelta
from time import sleep
from itertools import cycle
import requests

import pandas as pd
import numpy as np

from urllib.request import urlopen

from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.traceback import Traceback

from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive, var
from textual.widgets import Button, DataTable, Footer, Header, Static, TextLog, Tree, Markdown, TabbedContent, TabPane
from textual.widgets.tree import TreeNode

import rest_client as ftrc
import ftui_client as ftuic

from ftui_screens import CandlestickScreen, TradeInfoScreen, ProfitChartPanel
import plotext as f

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
    active_tab = reactive("open-trades-tab")
    updating = False
    last_update = None
    
    loglimit = 100
    
    func_map = {
        "open-trades-tab":"update_open_trades_tab",
        "closed-trades-tab":"update_closed_trades_tab",
        "summary-trades-tab":"update_summary_trades_tab",
        "tag-summary-tab":"update_tag_summary_tab",
        "charts-tab":"update_charts_tab",
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

    def _get_active_tab_id(self):
        active_tab_id = self.query_one("#right").get_child_by_type(TabbedContent).active
        return active_tab_id

    def _get_tab(self, tab_id):
        return next(self.query(f"#{tab_id}").results(TabPane))

    def _get_bot_id_from_tree(self):
        tree = self.query_one(Tree)
        bot_id = str(tree.cursor_node.label)
        return bot_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="parent-container"):
            with Container(id="left"):
                yield Static("[@click='app.bell']Dashboard[/]")
                yield Tree("Clients", id="client-view")
            with Container(id="right"):
                with Container(id="trades-summary"):
                    yield Static("Select a bot from the client list...", id="sel-bot-title")
                    yield DataTable(id="trades-summary-table", show_cursor=False)

                with TabbedContent(initial="open-trades-tab"):
                    
                    #with TabPane("Summary", id="all-bot-summary-tab")
                    #    yield DataTable(id="all-bot-summary-table")

                    with TabPane("Open Trades", id="open-trades-tab"):
                        yield DataTable(id="open-trades-table")

                    with TabPane("Closed Trades", id="closed-trades-tab"):
                        yield DataTable(id="closed-trades-table")
                    
                    with TabPane("Tag Summary", id="tag-summary-tab"):
                        yield DataTable(id="tag-summary-table")
                        
                    with TabPane("Charts", id="charts-tab"):
                        yield Container(id="chart")
                    
                    with TabPane("Logs", id="logs-tab"):
                        yield TextLog(id="log", wrap=True)
                        # yield Container(id="sysinfo-panel")

                    # with TabPane("Help", id="help-tab"):
                    #     yield Markdown("#Hello", id="help")

                    with TabPane("Debug", id="debug-tab"):
                        yield TextLog(id="debug-log")

        yield Footer()

    @classmethod
    def add_clients(self, node: TreeNode, clients: dict) -> None:
        from rich.highlighter import ReprHighlighter
        highlighter = ReprHighlighter()

        def add_node(name: str, node: TreeNode, data: object) -> None:
            if isinstance(data, dict): # client_dict
                node._label = Text(f"{name}")
                for cl_name, ftui_client in data.items():
                    new_node = node.add("")
                    add_node(f"{cl_name}", new_node, ftui_client)
            elif isinstance(data, ftuic.FTUIClient): # actual client
                node._label = Text(f"{name}")
                node._allow_expand = False

        add_node("Clients", node, clients)

    def on_mount(self) -> None:
        tree = self.query_one(Tree)
        self.add_clients(tree.root, client_dict)
        tree.root.expand()
        tree.focus()

        self.query_one("#debug-log").write(Text(f"{datetime.now(tz=timezone.utc)} : FTUI started"))
        
        self.watch(self.query_one("#right").get_child_by_type(TabbedContent), "active", self.monitor_active_tab)
        
        self.update_one_sec_render = self.set_interval(
            1, self.update_per_sec
        )

        self.update_five_sec_render = self.set_interval(
            5, self.update_per_five_sec
        )

    async def update_per_sec(self):
        active_tab_id = self._get_active_tab_id()
        bot_id = self._get_bot_id_from_tree()
        
        if bot_id is not None and (bot_id != "Clients"):
            self.updating = True
            
            self.update_trades_summary(bot_id)
            
            if ("open-trades-tab" == active_tab_id):
                self.update_open_trades_tab(active_tab_id, bot_id)
        
        self.updating = False
        
    async def update_per_five_sec(self):
        active_tab_id = self._get_active_tab_id()
        bot_id = self._get_bot_id_from_tree()
        
        if bot_id is not None:
            if ("logs-tab" == active_tab_id):
                self.update_logs_tab(active_tab_id, bot_id)

    def watch_show_clients(self, show_clients: bool) -> None:
        self.set_class(show_clients, "-show-clients")

    #def watch_active_tab(self, active_tab: str) -> None:
    #    self.query_one("#sel-bot-title").update(active_tab)

    def action_toggle_clients(self) -> None:
        self.show_clients = (
            not self.show_clients
        )

    def action_show_tab(self, tab: str) -> None:
        self.get_child_by_type(TabbedContent).active = tab
        bot_id = self._get_bot_id_from_tree()
        self.update_tab(active_tab_id, bot_id)

    def action_show_trade_info_dialog(self, trade_id, cl_name):
        tis = TradeInfoScreen()
        tis.trade_id = trade_id
        tis.client = client_dict[cl_name]
        self.push_screen(tis)

    def action_show_pair_candlestick_dialog(self, pair, cl_name):
        css = CandlestickScreen()
        css.pair = pair
        css.client = client_dict[cl_name]
        self.push_screen(css)

    def monitor_active_tab(self, active_tab_id):
        bot_id = self._get_bot_id_from_tree()
        self.debug(f"Active tab changed: {active_tab_id}")
        self.update_tab(active_tab_id, bot_id)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        event.stop()

        active_tab_id = self._get_active_tab_id()
        bot_id = str(event.node.label)
        
        self.query_one("#sel-bot-title").update(bot_id)
        self.update_trades_summary(bot_id)
        self.update_tab(active_tab_id, bot_id)
        # self.update_sysinfo_header(bot_id)
    
    # @work(exclusive=True)
    def update_tab(self, tab_id, bot_id):
        if bot_id != "Clients":
            self.active_tab = tab_id
            # self.run_worker(self.tab_select_func(tab_id, bot_id), exclusive=True)
            self.tab_select_func(tab_id, bot_id)

    def update_trades_summary(self, bot_id):
        cl = client_dict[bot_id]
        data = self.build_trades_summary(cl)
        self.replace_trades_summary_header(data)

    # def update_sysinfo_header(self, bot_id):
    #     cl = client_dict[bot_id]        
    #     data = self.build_sysinfo_header(cl)
    #     self.replace_sysinfo_header(data)
        
    def update_open_trades_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = self._get_tab(tab_id)
        data = self.build_open_trade_summary(cl)
        self.replace_summary_table(data, tab)

    def update_closed_trades_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = self._get_tab(tab_id)
        data = self.build_closed_trade_summary(cl) 
        self.replace_summary_table(data, tab)

    def update_tag_summary_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = self._get_tab(tab_id)
        data = self.build_enter_tag_summary(cl)
        self.replace_summary_table(data, tab)

    def update_charts_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = self._get_tab(tab_id)
        chart = self.build_profit_chart(cl)
        self.replace_chart(chart, tab)

    def update_logs_tab(self, tab_id, bot_id):
        cl = client_dict[bot_id]
        tab = self._get_tab(tab_id)
        logs = cl.get_logs(limit=self.loglimit)
        self.replace_logs(logs, tab)

    # def update_help_tab(self, tab_id, bot_id):
    #     cl = client_dict[bot_id]
    #     return "foo"

    def replace_trades_summary_header(self, data):
        dt = self.query_one("#trades-summary-table")
        dt.clear(columns=True)

        rows = iter(data)
        try:
            dt.add_columns(*next(rows))
            dt.add_rows(rows)
        except Exception as e:
            raise e
        dt.refresh()

    # def replace_sysinfo_header(self, data):
    #     panel = self.query_one("#sysinfo-panel")
    #     for c in panel.children:
    #         c.remove()
    #     sysinfo_group = Group(*data)
    #     panel.mount(sysinfo_group)

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
        
        return dt

    def replace_chart(self, chart, tab):
        chart_container = tab.get_child_by_type(Container)
        for c in chart_container.children:
            c.remove()
        chart_container.mount(chart)

    def replace_logs(self, logs, tab):
        log = tab.query_one("#log")
        log.clear()
        log.write(logs)

    def build_sysinfo_header(self, ftuic):
        sysinfo = ftuic.get_sys_info()
        syslist = []
        
        progress_table = Table.grid(expand=True, pad_edge=True)
        
        progress_cpu = Progress(
            "{task.description}",
            BarColumn(bar_width=None, complete_style=Style(color="red"), finished_style=Style(color="red")),
            TextColumn("[red]{task.percentage:>3.0f}%"),
            expand=True,
        )
        
        progress_ram = Progress(
            "{task.description}",
            BarColumn(bar_width=None, complete_style=Style(color="magenta"), finished_style=Style(color="magenta")),
            TextColumn("[magenta]{task.percentage:>3.0f}%", style=Style(color="magenta")),
            expand=True,
        )
        
        progress_table.add_row(
            progress_cpu,
            progress_ram
        )
        
        if 'cpu_pct' in sysinfo:
            for cpux in sysinfo['cpu_pct']:
                cpujob = progress_cpu.add_task("[cyan] CPU")
                progress_cpu.update(cpujob, completed=cpux)

            job2 = progress_ram.add_task("[cyan] RAM")
            progress_ram.update(job2, completed=sysinfo['ram_pct'])

            syslist.append(Rule(title=f"{ftuic.name} [{ftuic.url}:{ftuic.port}]", style=Style(color="cyan"), align="left"))
            syslist.append(progress_table)

        return syslist

    def build_trades_summary(self, ftuic):
        row_data = [
            ("# Trades", "Open Profit", "W/L", "Winrate", "Exp.",
             "Exp. Rate", "Med. W", "Med. L", "Total"),
        ]

        all_open_profit = 0
        all_profit = 0
        all_wins = 0
        all_losses = 0
        
        tot_profit = 0

        status = ftuic.get_open_trades()
        if status is not None:
            for ot in status:
                tot_profit = tot_profit + ot['profit_abs']
        
#            max_open_trades = ftuic.max_open_trades
        #if (max_open_trades > 0):
            #risk = ftuic.calc_risk()
        
        tp = []
        tpw = []
        tpl = []
        for at in ftuic.get_all_closed_trades():
            profit = float(at['profit_abs'])
            tp.append(profit)
            if profit > 0:
                tpw.append(profit)
            else:
                tpl.append(abs(profit))
        
        mean_prof = 0
        mean_prof_w = 0
        mean_prof_l = 0
        median_prof = 0
        
        if len(tp) > 0:
            mean_prof = round(statistics.mean(tp), 2)
        
        if len(tpw) > 0:
            mean_prof_w = round(statistics.mean(tpw), 2)
            median_win = round(statistics.median(tpw), 2)
        else:
            mean_prof_w = 0
            median_win = 0
        
        if len(tpl) > 0:
            mean_prof_l = round(statistics.mean(tpl), 2)
            median_loss = round(statistics.median(tpl), 2)
        else:
            mean_prof_l = 0
            median_loss = 0
        
        if (len(tpw) == 0) and (len(tpl) == 0):
            winrate = 0
            loserate = 0
        else:
            winrate = (len(tpw) / (len(tpw) + len(tpl))) * 100
            loserate = 100 - winrate
        
        expectancy = 1
        if mean_prof_w > 0 and mean_prof_l > 0:
            expectancy = (1 + (mean_prof_w / mean_prof_l)) * (winrate / 100) - 1
        else:
            if mean_prof_w == 0:
                expectancy = 0
        
        expectancy_rate = ((winrate/100) * mean_prof_w) - ((loserate/100) * mean_prof_l)
                
        t = ftuic.get_total_profit()

        pcc = round(float(t['profit_closed_coin']), 2)
        all_open_profit = all_open_profit + tot_profit
        all_profit = all_profit + pcc
        all_wins = all_wins + t['winning_trades']
        all_losses = all_losses + t['losing_trades']

        row_data.append((
            f"[cyan]{int(t['trade_count'])-int(t['closed_trade_count'])}[white]/[magenta]{t['closed_trade_count']}",
            f"[red]{round(tot_profit, 2)}" if tot_profit <= 0 else f"[green]{round(tot_profit, 2)}",            
            f"[green]{t['winning_trades']}/[red]{t['losing_trades']}",
            f"[cyan]{round(winrate, 1)}",
            f"[magenta]{round(expectancy, 2)}",
            f"[red]{round(expectancy_rate, 2)}" if expectancy_rate <= 0 else f"[green]{round(expectancy_rate, 2)}",
            # f"[red]{mean_prof}" if mean_prof <= 0 else f"[green]{mean_prof}",
            f"[green]{median_win}",
            f"[red]{median_loss}",
            f"[red]{pcc}" if pcc <= 0 else f"[green]{pcc}",
        ))
        
        # row_data.append((
        #     "",
        #     f"[red]{round(all_open_profit, 2)}" if all_open_profit <= 0 else f"[green]{round(all_open_profit, 2)}",
        #     f"[green]{all_wins}/[red]{all_losses}",
        #     "",
        #     "",
        #     "",
        #     "",
        #     "",
        #     f"[red]{round(all_profit, 2)}" if all_profit <= 0 else f"[green]{round(all_profit, 2)}",
        # ))

        return row_data

    def build_open_trade_summary(self, ftuic):
        row_data = [
            ("ID", "Pair", "Profit %", "Profit", "Dur.", "S/L", "Entry"),
        ]
        fmt = "%Y-%m-%d %H:%M:%S"

        trades = ftuic.get_open_trades()
        if trades is not None:
            for t in trades[:20]:
                otime = datetime.strptime(t['open_date'], fmt).astimezone(tz=timezone.utc)
                ctime = datetime.now(tz=timezone.utc)
                
                pairstr = t['pair'] + ('*' if (t['open_order_id'] is not None and t['close_rate_requested'] is None) else '') + ('**' if (t['close_rate_requested'] is not None) else '')
                rpfta = round(float(t['profit_abs']), 2)
                t_dir = "S" if t['is_short'] else "L"
                
                row_data.append((
                    f"[@click=show_trade_info_dialog('{t['trade_id']}', '{ftuic.name}')]{t['trade_id']}[/]",
                    f"{pairstr}",
                    f"[red]{t['profit_pct']}" if t['profit_pct'] <= 0 else f"[green]{t['profit_pct']}",
                    f"[red]{rpfta}" if rpfta <= 0 else f"[green]{rpfta}",
                    f"{str(ctime-otime).split('.')[0]}",
                    f"{t_dir}",
                    f"{t['enter_tag']}",
                ))

        return row_data

    def build_closed_trade_summary(self, ftuic):
        row_data = [
            ("ID", "Pair", "Profit %", "Profit", "Open Date", "Dur.", "Entry", "Exit"),
        ]
        fmt = "%Y-%m-%d %H:%M:%S"

        trades = ftuic.get_all_closed_trades()
        if trades is not None:
            for t in trades[:20]:
                otime = datetime.strptime(t['open_date'], fmt).astimezone(tz=timezone.utc)
                ctime = datetime.strptime(t['close_date'], fmt).astimezone(tz=timezone.utc)
                rpfta = round(float(t['profit_abs']), 2)

                row_data.append((
                    f"[@click=show_trade_info_dialog('{t['trade_id']}', '{ftuic.name}')]{t['trade_id']}[/]",
                    f"[@click=show_pair_candlestick_dialog('{t['pair']}', '{ftuic.name}')]{t['pair']}[/]",
                    f"[red]{t['profit_pct']}" if t['profit_pct'] <= 0 else f"[green]{t['profit_pct']}",
                    f"[red]{rpfta}" if rpfta <= 0 else f"[green]{rpfta}",
                    f"{str(otime).split('+')[0]}",
                    f"{str(ctime-otime).split('.')[0]}",
                    f"{t['enter_tag']}",
                    f"{t['exit_reason']}"
                ))

        return row_data

    def build_profit_chart(self, ftuic):
        pc = ProfitChartPanel()
        pc.client = ftuic
        pc.title = ftuic.name
        return pc

    def build_enter_tag_summary(self, ftuic):
        row_data = [
            ("Tag", "W/L", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit"),
        ]
        fmt = "%Y-%m-%d %H:%M:%S"

        # get dict of bot to trades
        trades_by_tag = {}

        for at in ftuic.get_all_closed_trades():
            if at['enter_tag'] not in trades_by_tag:
                trades_by_tag[at['enter_tag']] = []
            
            trades_by_tag[at['enter_tag']].append(at)

        for tag, trades in trades_by_tag.items():
            t_profit = 0.0
            
            tot_trade_dur = 0
            avg_win_trade_dur = 0
            avg_loss_trade_dur = 0
            win_trade_dur = 0
            num_win = 0
            loss_trade_dur = 0
            num_loss = 0

            for t in trades:
                profit = float(t['profit_abs'])
                t_profit += profit
                tdur = (datetime.strptime(t['close_date'], dfmt) - datetime.strptime(t['open_date'], dfmt)).total_seconds()
                tot_trade_dur = tot_trade_dur + tdur
                
                if profit > 0:
                    win_trade_dur = win_trade_dur + tdur
                    num_win = num_win + 1
                else:
                    loss_trade_dur = loss_trade_dur + tdur
                    num_loss = num_loss + 1

            t_profit = round(t_profit, 2)

            avg_trade_dur = str(timedelta(seconds = round(tot_trade_dur / len(trades), 0)))
            if num_win > 0:
                avg_win_trade_dur = str(timedelta(seconds = round(win_trade_dur / num_win, 0)))
            if num_loss > 0:
                avg_loss_trade_dur = str(timedelta(seconds = round(loss_trade_dur / num_loss, 0)))

            row_data.append((
                f"[white]{tag}",
                f"[green]{num_win}/[red]{num_loss}",
                f"[yellow]{avg_trade_dur}",
                f"[green]{avg_win_trade_dur}",
                f"[red]{avg_loss_trade_dur}",
                f"[red]{t_profit}" if t_profit <= 0 else f"[green]{t_profit}",
            ))

        return row_data

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