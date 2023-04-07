from rich.text import Text
from rich.jupyter import JupyterMixin

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.screen import Screen

from textual.reactive import var, reactive
from textual.widgets import Button, DataTable, Footer, Header, Static

import pandas as pd
import gnuplotlib as gp
import termplotlib as tpl
import numpy as np
import subprocess

from rich.ansi import AnsiDecoder
from rich.console import Group
import plotext as plt
import yfinance as yf

import ftui_client as ftuic

class BasicModal(Screen):
    BINDINGS = [
        ("escape", "close_dialog", "Close Dialog"),
    ]    

    client: ftuic.FTUIClient = None

    def action_close_dialog(self) -> None:
        self.app.pop_screen()

class CandlestickScreen(BasicModal):
    pair: str = "BTC/USDT"
    limit: int = 200

    class plotextMixin(JupyterMixin):

        def __init__(self, width=0, height=0, title = "", candles = pd.DataFrame()):
            self.decoder = AnsiDecoder()
            self.width = width
            self.height = height
            self.title = title
            self.candles = candles

        def __rich_console__(self, console, options):
            self.width = options.max_width or console.width
            self.height = options.height or console.height
            
            canvas = self.build_candlestick_plot_screen(self.width, self.height, self.title)
            
            self.rich_canvas = Group(*self.decoder.decode(canvas))
            yield self.rich_canvas

        def build_candlestick_plot_screen(self, width, height, title):
            plt.cld()

            dfmt = "Y-m-d H:M:S"
            plt.date_form(dfmt)

            #plt.subplots(2, 1)
            #plt.subplot(1, 1)
            plt.date_form(dfmt)
            plt.candlestick(self.candles['date'], self.candles)
            plt.scatter(self.candles['date'], self.candles['ema_8'], label = "EMA(8)")
            plt.scatter(self.candles['date'], self.candles['ema_20'], label = "EMA(20)")
            # plt.plotsize(self.parent.size.width * 0.9, self.parent.size.height * 0.55)
            plt.plotsize(width, height * 0.85)

            plt.title(title)
            plt.xlabel("Date")
            plt.ylabel("Price")
            plt.theme('dark')

            #plt.subplot(2, 1)
            #plt.date_form(dfmt)
            #plt.bar(self.candles['date'], self.candles['volume'])
            ## plt.plotsize(self.parent.size.width * 0.9, self.parent.size.height * 0.25)
            #plt.plotsize(width * 0.9, height * 0.25)

            #plt.xlabel("Date")
            #plt.ylabel("Volume")
            # plt.theme('dark')
            
            return plt.build()

    def compose(self) -> ComposeResult:
        candles = self.get_candles()
        plot = self.plotextMixin(width=self.parent.size.width, height=self.parent.size.height, title = self.pair, candles = candles)
        main = Static(plot)
        yield Container(
            main,
            id="dt-dialog",
        )
        yield Footer()

    def get_candles(self):
        return self.client.get_pair_dataframe(self.pair, limit=self.limit)

class DataFrameScreen(BasicModal):
    pair: str = "BTC/USDT"
    data: pd.DataFrame = pd.DataFrame()

    def compose(self) -> ComposeResult:
        main = self.build_dataframe_screen(self.data)
        yield Container(
            main,
            id="dt-dialog",
        )
        yield Footer()    

    def build_dataframe_screen(self, df) -> DataTable:
        dt = DataTable(classes="full-width")
        
        dt.clear(columns=True)

        dt.add_columns(*df.columns)
        for row in df.itertuples(index=False):
            dt.add_row(*[str(x) for x in row])
        return dt

class TradeInfoScreen(BasicModal):
    trade_id: int = "None"

    def compose(self) -> ComposeResult:
        trade_info = self.client.get_trade_info(self.trade_id)
        main, two, three = self.build_trade_info(trade_info)
        yield Container(
            main,
            two, 
            three,
            id="info-dialog",
        )
        yield Footer()
    
    def build_trade_info(self, trade_info):
        main_text = (
            f"[b]Trade Id     : " + f"{self.trade_id}\n"
            f"[b]Pair         : " + f"{trade_info['pair']}\n"
            f"[b]Open Date    : " + f"{trade_info['open_date']}\n"
            f"[b]Entry Tag    : " + f"{trade_info['enter_tag']}\n"
            f"[b]Stake        : " + f"{trade_info['stake_amount']} {trade_info['quote_currency']}\n"
            f"[b]Amount       : " + f"{trade_info['amount']}\n"
            f"[b]Open Rate    : " + f"{trade_info['open_rate']}\n"
            f"[b]Close Rate   : " + f"{trade_info['close_rate']}\n"
            f"[b]Close Date   : " + f"{trade_info['close_date']}\n"
            f"[b]Close Profit : " + f"{trade_info['close_profit_abs']} ({trade_info['close_profit_pct']}%)\n"
        )

        two_text = (
            f"[b]Stoploss         :  {trade_info['stop_loss_pct']} ({trade_info['stop_loss_abs']})\n"
            f"[b]Initial Stoploss :  {trade_info['initial_stop_loss_pct']} ({trade_info['initial_stop_loss_abs']})\n"
        )

        three_text = (
            # f"[b]Orders:  {self.trade_id}\n"
            ", ".join(list(trade_info.keys()))
        )

        main = Static(main_text, classes="box", id="main-left")
        two = Static(two_text, classes="box", id="two")
        three = Static(three_text, classes="box", id="three")

        return main, two, three
