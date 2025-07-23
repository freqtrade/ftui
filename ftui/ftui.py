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

    ftui -y config.yaml

"""

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from textual import work
from textual.app import App
from textual.logging import TextualHandler
from textual.reactive import reactive, var

import ftui.ftui_client as ftuic
import ftui.ftui_helpers as fth
from ftui.screens.dashboard_screen import DashboardScreen
from ftui.screens.help_screen import HelpScreen
from ftui.screens.main_bot_screen import MainBotScreen
from ftui.screens.settings_screen import SettingsScreen

urlre = r"^\[([a-zA-Z0-9]+)\]*([a-zA-Z0-9\-._~%!$&'()*+,;=]+)?:([ a-zA-Z0-9\-._~%!$&'()*+,;=]+)@?([a-z0-9\-._~%]+|\[[a-f0-9:.]+\]|\[v[a-f0-9][a-z0-9\-._~%!$&'()*+,;=:]+\]):([0-9]+)?"

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
    A spiritual successor to frogtrade9000,
    written originally by @froggleston.
    """

    CSS_PATH = "freqtext.css"
    BINDINGS = [
        ("d", "switch_ftui_mode('dashboard')", "Dashboard"),
        ("b", "switch_ftui_mode('bots')", "View Bots"),
        ("s", "switch_ftui_mode('settings')", "Settings"),
        ("h", "switch_ftui_mode('help')", "Help"),
        ("q", "quit", "Quit"),
    ]

    show_clients = var(True)
    active_tab = reactive("open-trades-tab")
    updating = False
    last_update = None

    settings = {}
    debug_mode = False

    client_dict = {}
    clients_disabled = set()
    client_dfs = {}

    DFMT = "%Y-%m-%d %H:%M:%S"
    TZFMT = "%Y-%m-%d %H:%M:%S%z"

    loglimit = 100

    # # setup screens
    # dash_screen = DashboardScreen()

    # bot_screen = MainBotScreen()

    # settings_screen = SettingsScreen()
    # # settings_screen.set_settings(settings)

    # help_screen = HelpScreen()

    MODES = {
        "dashboard": DashboardScreen,
        "bots": MainBotScreen,
        "settings": SettingsScreen,
        "help": HelpScreen,
    }

    # supported colours: https://textual.textualize.io/api/color/
    COLOURS = fth.FtuiColours()

    def set_client_dict(self, client_dict):
        self.client_dict = client_dict

    def set_settings(self, args):
        self.settings = args

        if self.settings.colours:
            self.set_colours(self.settings.colours)

    def set_colours(self, colours):
        self.COLOURS.set_colours(colours)

    def on_mount(self) -> None:
        self.switch_mode("dashboard")

        self.update_five_sec_render = self.set_interval(5, self.update_per_five_sec)

    async def update_per_five_sec(self):
        self.update_all_dfs()

    def _get_open_trade_dataframe(self, ftuic):
        row_data = []

        trades = ftuic.get_open_trades()
        if trades is not None:
            for t in trades:
                otime = datetime.strptime(f"{t['open_date']}+00:00", self.app.TZFMT)
                ctime = datetime.now(tz=timezone.utc)

                open_orders = (
                    t["has_open_orders"]
                    if "has_open_orders" in t
                    else (t["open_order_id"] is not None)
                )

                num_orders = len(t["orders"]) if "orders" in t else 0

                suff = ""
                if open_orders and t["close_rate_requested"] is None:
                    suff = " *"

                if t["close_rate_requested"] is not None:
                    suff = " **"

                pairstr = f"{t['pair']}{suff}"
                rpfta = round(float(t["profit_abs"]), 2)
                t_dir = "S" if t["is_short"] else "L"
                stop_profit = t['stop_loss_pct']

                max_profit = 0
                if t["max_rate"] is not None and t['max_rate'] != 0:
                    max_profit = round(
                        ((t["max_rate"] - t["open_rate"]) / t["max_rate"]) * 100, 2
                    )

                row_data.append(
                    (
                        ftuic.name,
                        t["trade_id"],
                        pairstr,
                        t["open_rate"],
                        t["current_rate"],
                        stop_profit,
                        max_profit,
                        t["profit_pct"],
                        rpfta,
                        ctime - otime,
                        t_dir,
                        t["enter_tag"],
                        t["open_date"],
                        t["stake_amount"],
                        t["leverage"],
                        num_orders,
                    )
                )

        df = pd.DataFrame(
            row_data,
            columns=[
                "Bot",
                "ID",
                "Pair",
                "Open Rate",
                "Current Rate",
                "Stop %",
                "Max %",
                "Profit %",
                "Profit",
                "Dur.",
                "S/L",
                "Entry",
                "Open Date",
                "Stake Amount",
                "Leverage",
                "# Orders",
            ],
        )

        df = df.sort_values(by="ID", ascending=False)

        return df

    def _get_closed_trade_dataframe(self, ftuic):
        row_data = []

        trades = ftuic.get_all_closed_trades()
        if trades is not None:
            for t in trades:
                otime = datetime.strptime(t["open_date"], self.DFMT)
                ctime = datetime.strptime(t["close_date"], self.DFMT)

                pairstr = t["pair"]
                rpfta = round(float(t["profit_abs"]), 2)

                row_data.append(
                    (
                        ftuic.name,
                        t["trade_id"],
                        pairstr,
                        t["profit_pct"],
                        rpfta,
                        otime,
                        ctime,
                        ctime - otime,
                        t["enter_tag"],
                        t["exit_reason"],
                        t["open_rate"],
                        t["close_rate"],
                        t["stake_amount"],
                        t["leverage"],
                    )
                )

        df = pd.DataFrame(
            row_data,
            columns=[
                "Bot",
                "ID",
                "Pair",
                "Profit %",
                "Profit",
                "Open Date",
                "Close Date",
                "Dur.",
                "Entry",
                "Exit",
                "Open Rate",
                "Close Rate",
                "Stake Amount",
                "Leverage",
            ],
        )

        return df

    def _get_enter_tag_dataframe(self, ftuic):
        row_data = []

        # get dict of bot to trades
        trades_by_tag = {}

        for at in ftuic.get_all_closed_trades():
            if at["enter_tag"] not in trades_by_tag:
                trades_by_tag[at["enter_tag"]] = []

            trades_by_tag[at["enter_tag"]].append(at)

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
                profit = float(t["profit_abs"])
                t_profit += profit
                tdur = (
                    datetime.strptime(t["close_date"], self.DFMT)
                    - datetime.strptime(t["open_date"], self.DFMT)
                ).total_seconds()
                tot_trade_dur = tot_trade_dur + tdur

                if profit > 0:
                    win_trade_dur = win_trade_dur + tdur
                    num_win = num_win + 1
                else:
                    loss_trade_dur = loss_trade_dur + tdur
                    num_loss = num_loss + 1

            t_profit = round(t_profit, 2)

            avg_trade_dur = str(timedelta(seconds=round(tot_trade_dur / len(trades), 0)))

            if num_win > 0:
                avg_win_trade_dur = str(timedelta(seconds=round(win_trade_dur / num_win, 0)))
            if num_loss > 0:
                avg_loss_trade_dur = str(timedelta(seconds=round(loss_trade_dur / num_loss, 0)))

            row_data.append(
                (
                    tag,
                    num_win,
                    num_loss,
                    avg_trade_dur,
                    avg_win_trade_dur,
                    avg_loss_trade_dur,
                    t_profit,
                )
            )

        df = pd.DataFrame(
            row_data,
            columns=[
                "Tag",
                "# Win",
                "# Loss",
                "Avg Dur.",
                "Avg Win Dur.",
                "Avg Loss Dur.",
                "Profit",
            ],
        )

        return df

    def _get_performance_dataframe(self, ftuic):
        row_data = []

        data = ftuic.get_performance()
        if data is not None:
            for t in data:
                pairstr = t["pair"]
                rpfta = round(float(t["profit_abs"]), 2)

                row_data.append(
                    (
                        pairstr,
                        t["count"],
                        t["profit_pct"],
                        rpfta,
                    )
                )

        df = pd.DataFrame(row_data, columns=["Pair", "# Trades", "Avg Profit %", "Total Profit"])

        return df

    @work(group="df_updater_worker", exclusive=False, thread=True)
    def update_all_dfs(self):
        all_closed_df = pd.DataFrame()

        for name, cl in self.client_dict.items():
            if name not in self.clients_disabled:
                op_data = self._get_open_trade_dataframe(cl)
                cl_data = self._get_closed_trade_dataframe(cl)
                tag_data = self._get_enter_tag_dataframe(cl)
                perf_data = self._get_performance_dataframe(cl)

                if cl.name not in self.client_dfs:
                    self.client_dfs[name] = {}

                self.client_dfs[name]["op_data"] = op_data
                self.client_dfs[name]["cl_data"] = cl_data
                self.client_dfs[name]["tag_data"] = tag_data
                self.client_dfs[name]["perf_data"] = perf_data

                if cl_data is not None and not cl_data.empty:
                    all_closed_df = pd.concat([all_closed_df, cl_data])

        self.client_dfs["all_closed"] = all_closed_df

    def watch_show_clients(self, show_clients: bool) -> None:
        self.set_class(show_clients, "-show-clients")

    # ACTIONS
    async def action_switch_ftui_mode(self, mode) -> None:
        await self.switch_mode(mode)


def setup(args):
    config = args.config
    client_dict = {}

    print(__doc__)

    pool_connections = 20
    if args.pool_connections:
        pool_connections = args.pool_connections

    pool_maxsize = 10
    if args.pool_maxsize:
        pool_maxsize = args.pool_maxsize

    if args.yaml:
        for s in args.servers:
            try:
                ftui_client = ftuic.FTUIClient(
                    name=s["name"] if "name" in s else None,
                    url=s["ip"],
                    port=s["port"],
                    username=s["username"],
                    password=s["password"],
                    config_path=config,
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                )

                client_dict[ftui_client.name] = ftui_client
            except Exception as e:
                raise RuntimeError("Cannot create freqtrade client") from e
    else:
        if config is not None:
            try:
                ftui_client = ftuic.FTUIClient(
                    config_path=config,
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                )
                client_dict[ftui_client.name] = ftui_client
            except Exception as e:
                raise RuntimeError("Cannot create freqtrade client") from e
        else:
            raise RuntimeError("No config or YAML file specified")

    if not client_dict:
        raise Exception("No valid clients specified in --config or --yaml options")

    return client_dict


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose debugging mode")

    parser.add_argument("-c", "--config", nargs="?", help="Config to parse")
    parser.add_argument("--pool_connections", nargs="?", default=20, help="Number of pool connections")
    parser.add_argument("--pool_maxsize", nargs="?", default=10, help="Pool cache maxsize")

    parser.add_argument(
        "-y", "--yaml", nargs="?", help="Supply a YAML file instead of command line arguments."
    )

    parser.add_argument("--debug", nargs="?", help="Debug mode")

    args = parser.parse_args()

    if args.yaml is not None:
        import yaml

        with open(args.yaml, "r") as yamlfile:
            args = fth.dotdict(yaml.safe_load(yamlfile))
            args.yaml = True

    client_dict = setup(args)

    ftapp = FreqText()
    ftapp.set_client_dict(client_dict)
    ftapp.set_settings(args)

    if args.debug:
        ftapp.debug_mode = True

    print("\nStarting FTUI - preloading all dataframes...", end="")

    all_closed_df = pd.DataFrame()

    for name, cl in client_dict.items():
        print("", end=".", flush=True)

        op_data = ftapp._get_open_trade_dataframe(cl)
        cl_data = ftapp._get_closed_trade_dataframe(cl)
        tag_data = ftapp._get_enter_tag_dataframe(cl)
        perf_data = ftapp._get_performance_dataframe(cl)

        if cl.name not in ftapp.client_dfs:
            ftapp.client_dfs[name] = {}

        ftapp.client_dfs[name]["op_data"] = op_data
        ftapp.client_dfs[name]["cl_data"] = cl_data
        ftapp.client_dfs[name]["tag_data"] = tag_data
        ftapp.client_dfs[name]["perf_data"] = perf_data

        if cl_data is not None and not cl_data.empty:
            all_closed_df = pd.concat([all_closed_df, cl_data])

    ftapp.client_dfs["all_closed"] = all_closed_df

    ftapp.run()


if __name__ == "__main__":
    main()
