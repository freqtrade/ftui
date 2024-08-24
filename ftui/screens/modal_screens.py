import pandas as pd
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Static,
)

import ftui.ftui_client as ftuic


class BasicModal(ModalScreen[int]):
    BINDINGS = [
        ("escape", "close_dialog", "Close Dialog"),
    ]

    client: ftuic.FTUIClient = None

    def action_close_dialog(self) -> None:
        self.app.pop_screen()


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
        main, two = self.build_trade_info(trade_info)
        with Container(main, two, id="info-dialog"):
            with Container(id="trade-info-footer"):
                yield Static("[Esc] to close")

    def build_trade_info(self, trade_info):
        main_text = (
            f"[b]Trade Id     : {self.trade_id}\n"
            f"[b]Pair         : {trade_info['pair']}\n"
            f"[b]Open Date    : {trade_info['open_date']}\n"
            f"[b]Entry Tag    : {trade_info['enter_tag']}\n"
            "[b]Stake        : "
            f"{trade_info['stake_amount']} "
            f"{trade_info['quote_currency']}\n"
            f"[b]Amount       : {trade_info['amount']}\n"
            f"[b]Open Rate    : {trade_info['open_rate']}\n"
        )

        if trade_info["close_profit_abs"] is not None:
            close_rate = trade_info["close_rate"]
            close_date = trade_info["close_date"]
            close_profit = f"{trade_info['close_profit_abs']} ({trade_info['close_profit_pct']}%)"

            main_text += (
                f"[b]Close Rate   : {close_rate}\n"
                f"[b]Close Date   : {close_date}\n"
                f"[b]Close Profit : {close_profit}\n"
            )

        two_text = (
            f"[b]Stoploss         : "
            f"{trade_info['stop_loss_pct']} ({trade_info['stop_loss_abs']})\n"
            f"[b]Initial Stoploss : "
            f"{trade_info['initial_stop_loss_pct']} ({trade_info['initial_stop_loss_abs']})\n"
        )

        # three_text = (7
        #     # f"[b]Orders:  {self.trade_id}\n"
        #     ", ".join(list(trade_info.keys()))
        # )

        main = Static(main_text, classes="box", id="trade-info-left")
        two = Static(two_text, classes="box", id="trade-info-right")
        # three = Static(three_text, classes="box", id="three")

        return main, two
