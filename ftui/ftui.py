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

import argparse, re, sys
from datetime import datetime, timezone, timedelta

import pandas as pd
import numpy as np

from rich.progress import Progress, BarColumn, TextColumn
from rich.rule import Rule
from rich.style import Style
from rich.table import Table

from textual import work
from textual.app import App
from textual.reactive import reactive, var

import ftui.ftui_client as ftuic
import ftui.ftui_helpers as fth

from ftui.ftui_screens import (
    HelpScreen,
    MainBotScreen,
    SettingsScreen,
    DashboardScreen,
    TradeInfoScreen
)

urlre = r"^\[([a-zA-Z0-9]+)\]*([a-zA-Z0-9\-._~%!$&'()*+,;=]+)?:([ a-zA-Z0-9\-._~%!$&'()*+,;=]+)@?([a-z0-9\-._~%]+|\[[a-f0-9:.]+\]|\[v[a-f0-9][a-z0-9\-._~%!$&'()*+,;=:]+\]):([0-9]+)?"

import logging
from textual.logging import TextualHandler

logging.basicConfig(
    level="NOTSET",
    handlers=[TextualHandler()],
)

client_logger = logging.getLogger("ft_rest_client")
client_logger.setLevel(logging.ERROR)
client_logger.removeHandler(sys.stdout)
client_logger.removeHandler(sys.stderr)
client_logger.addHandler(TextualHandler())

asyncio_logger = logging.getLogger("asyncio")
asyncio_logger.removeHandler(sys.stdout)
asyncio_logger.removeHandler(sys.stderr)
asyncio_logger.addHandler(TextualHandler())

args = None


class FreqText(App):
    """
    Freqtrade text interface based on Textual.
    A spiritual successor to frogtrade9000.
    """

    CSS_PATH = "freqtext.css"
    BINDINGS = [
        ("d", "switch_ftui_mode('dashboard')", "Dashboard"),
        ("b", "switch_ftui_mode('bots')", "View Bots"),
        ("s", "switch_ftui_mode('settings')", "Settings"),
        ("h", "switch_ftui_mode('help')", "Help"),
        ("q", "quit", "Quit"),
    ]

    # SCREENS = {"c_candles": CandlestickScreen(),
    #            "i_tradeinfo": TradeInfoScreen(),
    #            "c_profit": ProfitChartPanel()}

    show_clients = var(True)
    active_tab = reactive("open-trades-tab")
    updating = False
    last_update = None

    client_dict = {}
    client_dfs = {}

    DFMT = "%Y-%m-%d %H:%M:%S"
    TZFMT = "%Y-%m-%d %H:%M:%S%z"

    loglimit = 100

    ## setup screens
    dash_screen = DashboardScreen()

    bot_screen = MainBotScreen()

    settings_screen = SettingsScreen()
    settings_screen.set_args(args)

    help_screen = HelpScreen()

    MODES = {
        "dashboard": dash_screen,
        "bots": bot_screen,
        "settings": settings_screen,
        "help": help_screen,
    }

    def set_client_dict(self, client_dict):
        self.client_dict = client_dict


    def on_mount(self) -> None:
        self.switch_mode("dashboard")

        self.update_five_sec_render = self.set_interval(
            5, self.update_per_five_sec
        )

    async def update_per_five_sec(self):
        self.update_all_dfs()

    def _get_open_trade_dataframe(self, ftuic):
        row_data = []

        trades = ftuic.get_open_trades()
        if trades is not None:
            for t in trades:
                otime = datetime.strptime(t['open_date'], self.DFMT).astimezone(tz=timezone.utc)
                ctime = datetime.now(tz=timezone.utc)

                pairstr = t['pair'] # + ('*' if (t['open_order_id'] is not None and t['close_rate_requested'] is None) else '') + ('**' if (t['close_rate_requested'] is not None) else '')
                rpfta = round(float(t['profit_abs']), 2)
                t_dir = "S" if t['is_short'] else "L"
                stop_profit = round(((t['stop_loss_abs'] - t['open_rate']) / t['stop_loss_abs'])*100, 2)

                row_data.append((
                    ftuic.name,
                    t['trade_id'],
                    pairstr,
                    t['open_rate'],
                    t['current_rate'],
                    stop_profit,
                    t['profit_pct'],
                    rpfta,
                    ctime-otime,
                    t_dir,
                    t['enter_tag'],
                ))

        df = pd.DataFrame(
            row_data,
            columns= [
                "Bot", "ID", "Pair", "Open Rate", "Current Rate", "Stop %", "Profit %", "Profit", "Dur.", "S/L", "Entry"
            ]
        )

        df = df.sort_values(by='ID', ascending=False)

        return df


    def _get_closed_trade_dataframe(self, ftuic):
        row_data = []

        trades = ftuic.get_all_closed_trades()
        if trades is not None:
            for t in trades:
                otime = datetime.strptime(t['open_date'], self.DFMT).astimezone(tz=timezone.utc)
                ctime = datetime.strptime(t['close_date'], self.DFMT).astimezone(tz=timezone.utc)

                pairstr = t['pair'] # + ('*' if (t['open_order_id'] is not None and t['close_rate_requested'] is None) else '') + ('**' if (t['close_rate_requested'] is not None) else '')
                rpfta = round(float(t['profit_abs']), 2)

                row_data.append((
                    ftuic.name,
                    t['trade_id'],
                    pairstr,
                    t['profit_pct'],
                    rpfta,
                    otime,
                    ctime,
                    ctime-otime,
                    t['enter_tag'],
                    t['exit_reason'],
                ))

        df = pd.DataFrame(
            row_data,
            columns= [
                "Bot", "ID", "Pair", "Profit %", "Profit", "Open Date", "Close Date", "Dur.", "Entry", "Exit"
            ]
        )

        return df


    def _get_enter_tag_dataframe(self, ftuic):
        row_data = []

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
                tdur = (datetime.strptime(t['close_date'], self.DFMT) - datetime.strptime(t['open_date'], self.DFMT)).total_seconds()
                tot_trade_dur = tot_trade_dur + tdur

                if profit > 0:
                    win_trade_dur = win_trade_dur + tdur
                    num_win = num_win + 1
                else:
                    loss_trade_dur = loss_trade_dur + tdur
                    num_loss = num_loss + 1

            t_profit = round(t_profit, 2)


            wl = num_win
            avg_trade_dur = str(timedelta(seconds = round(tot_trade_dur / len(trades), 0)))
            if num_win > 0:
                avg_win_trade_dur = str(timedelta(seconds = round(win_trade_dur / num_win, 0)))
            if num_loss > 0:
                avg_loss_trade_dur = str(timedelta(seconds = round(loss_trade_dur / num_loss, 0)))
                wl = num_win/num_loss

            row_data.append((
                tag,
                num_win,
                num_loss,
                avg_trade_dur,
                avg_win_trade_dur,
                avg_loss_trade_dur,
                t_profit,
            ))

        df = pd.DataFrame(
            row_data,
            columns= [
                "Tag", "# Win", "# Loss", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit"
            ]
        )

        return df

    def _get_performance_dataframe(self, ftuic):
        row_data = []

        data = ftuic.get_performance()
        if data is not None:
            for t in data:
                pairstr = t['pair'] # + ('*' if (t['open_order_id'] is not None and t['close_rate_requested'] is None) else '') + ('**' if (t['close_rate_requested'] is not None) else '')
                rpfta = round(float(t['profit_abs']), 2)

                row_data.append((
                    pairstr,
                    t['count'],
                    t['profit_pct'],
                    rpfta,
                ))

        df = pd.DataFrame(
            row_data,
            columns= [
                "Pair", "# Trades", "Avg Profit %", "Total Profit"
            ]
        )

        return df


    @work(group="df_updater_worker", exclusive=False, thread=True)
    def update_all_dfs(self):
        all_closed_df = pd.DataFrame()

        for name, cl in self.client_dict.items():
            op_data = self._get_open_trade_dataframe(cl)
            cl_data = self._get_closed_trade_dataframe(cl)
            tag_data = self._get_enter_tag_dataframe(cl)
            perf_data = self._get_performance_dataframe(cl)

            if cl.name not in self.client_dfs:
                self.client_dfs[name] = {}

            self.client_dfs[name]['op_data'] = op_data
            self.client_dfs[name]['cl_data'] = cl_data
            self.client_dfs[name]['tag_data'] = tag_data
            self.client_dfs[name]['perf_data'] = perf_data

            if cl_data is not None and not cl_data.empty:
                all_closed_df = pd.concat([all_closed_df, cl_data])

        self.client_dfs['all_closed'] = all_closed_df


    def watch_show_clients(self, show_clients: bool) -> None:
        self.set_class(show_clients, "-show-clients")

    ## ACTIONS
    def action_switch_to_bot(self, bot_id) -> None:
        current_screen = self.screen

        for ts in current_screen.timers.keys():
            print(f"Pausing {current_screen.id} {ts}")
            current_screen.timers[ts].pause()

        self.switch_mode("bots")

        for ts in self.MODES["bots"].timers.keys():
            print(f"Resuming bots {ts}")
            self.MODES["bots"].timers[ts].resume()

        self.MODES['bots'].update_screen(bot_id)

    def action_switch_ftui_mode(self, mode) -> None:
        current_screen = self.screen

        for ts in current_screen.timers.keys():
            print(f"Pausing {current_screen.id} {ts}")
            current_screen.timers[ts].pause()

        for ts in self.MODES[mode].timers.keys():
            print(f"Resuming {mode} {ts}")
            self.MODES[mode].timers[ts].resume()

        self.switch_mode(mode)

    def action_update_chart(self, bot_id, pair) -> None:
        self.MODES['bots'].update_chart(bot_id, pair)

    def action_show_trade_info_dialog(self, trade_id, cl_name):
        tis = TradeInfoScreen()
        tis.trade_id = trade_id
        tis.client = self.client_dict[cl_name]
        self.push_screen(tis)

    # def update_sysinfo_header(self, bot_id):
    #     cl = client_dict[bot_id]
    #     data = self.build_sysinfo_header(cl)
    #     self.replace_sysinfo_header(data)

    # def replace_sysinfo_header(self, data):
    #     panel = self.query_one("#sysinfo-panel")
    #     for c in panel.children:
    #         c.remove()
    #     sysinfo_group = Group(*data)
    #     panel.mount(sysinfo_group)

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


def setup(args):
    config = args.config
    client_dict = {}

    print(__doc__)

    if args.servers is not None:
        if args.yaml:
            indicators = args.indicators

            num_servers = len(args.servers)
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
            num_servers = len(slist)
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

    return client_dict


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debugging mode")
    parser.add_argument("-c", "--config", nargs='?', help="Config to parse")
    parser.add_argument("-y", "--yaml", nargs='?', help="Supply a YAML file instead of command line arguments.")
    parser.add_argument("--debug", nargs="?", help="Debug mode")
    args = parser.parse_args()

    if args.yaml is not None:
        import yaml
        with open(args.yaml, 'r') as yamlfile:
            args = fth.dotdict(yaml.safe_load(yamlfile))
            args.yaml = True

    client_dict = setup(args)

    ftapp = FreqText()
    ftapp.set_client_dict(client_dict)

    print("\nStarting FTUI - preloading all dataframes...", end="")

    all_closed_df = pd.DataFrame()

    for name, cl in client_dict.items():
        print("", end = ".", flush=True)

        op_data = ftapp._get_open_trade_dataframe(cl)
        cl_data = ftapp._get_closed_trade_dataframe(cl)
        tag_data = ftapp._get_enter_tag_dataframe(cl)
        perf_data = ftapp._get_performance_dataframe(cl)

        if cl.name not in ftapp.client_dfs:
            ftapp.client_dfs[name] = {}

        ftapp.client_dfs[name]['op_data'] = op_data
        ftapp.client_dfs[name]['cl_data'] = cl_data
        ftapp.client_dfs[name]['tag_data'] = tag_data
        ftapp.client_dfs[name]['perf_data'] = perf_data

        if cl_data is not None and not cl_data.empty:
            all_closed_df = pd.concat([all_closed_df, cl_data])

    ftapp.client_dfs['all_closed'] = all_closed_df

    ftapp.run()


if __name__ == "__main__":
    main()
