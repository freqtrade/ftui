from datetime import datetime

import pandas as pd
import requests
from rich import box
from rich.table import Table
from rich.text import Text
from textual._color_constants import COLOR_NAME_TO_RGB
from textual.color import Color


class FtuiColours(dict[str, Color]):

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    REVERSED_COL_MAP = dict(map(reversed, COLOR_NAME_TO_RGB.items()))

    def __init__(self):
        super().__init__(
            {
                "pair_col": Color.parse("purple"),
                "bot_col": Color.parse("yellow"),
                "bot_start_col": Color.parse("white"),
                "trade_id_col": Color.parse("white"),
                "open_rate_col": Color.parse("white"),
                "current_rate_col": Color.parse("white"),
                "open_date_col": Color.parse("cyan"),
                "winrate_col": Color.parse("cyan"),
                "open_trade_num_col": Color.parse("cyan"),
                "closed_trade_num_col": Color.parse("purple"),
                "profit_chart_col": Color.parse("orange"),
                "link_col": Color.parse("yellow"),
                "candlestick_trade_text_col": Color.parse("orange"),
                "candlestick_trade_open_col": Color.parse("blue"),
                "candlestick_trade_close_col": Color.parse("purple"),
            }
        )

    def __getattr__(self, key):
        if key in self:
            return self.REVERSED_COL_MAP[self[key].rgb]
        raise AttributeError(key)

    def set_colours(self, colours):
        for k, v in colours.items():
            self[k] = Color.parse(v)


class dotdict(dict):
    """dot.notation access to dictionary attributes"""

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def red_or_green(val, justify="left"):
    if val <= 0:
        return Text(str(f"{val}"), style="red", justify=justify)
    else:
        return Text(str(f"{val}"), style="green", justify=justify)


def set_red_green_widget_colour(w, val):
    if val <= 0:
        w.styles.color = "red"
    else:
        w.styles.color = "green"


def _get_dataframe_data_from_client(client, client_dfs, data_type):
    if client.name in client_dfs and data_type in client_dfs[client.name]:
        return client_dfs[client.name][data_type].copy()
    return pd.DataFrame()


def get_open_dataframe_data(client, client_dfs):
    return _get_dataframe_data_from_client(client, client_dfs, "op_data")


def get_closed_dataframe_data(client, client_dfs):
    return _get_dataframe_data_from_client(client, client_dfs, "cl_data")


def get_tag_dataframe_data(client, client_dfs):
    return _get_dataframe_data_from_client(client, client_dfs, "tag_data")


def get_perf_dataframe_data(client, client_dfs):
    return _get_dataframe_data_from_client(client, client_dfs, "perf_data")


def daily_profit_table(client_dict, num_days_daily) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    table.add_column("Date", style="white", no_wrap=True)
    table.add_column("Fear", style="white", no_wrap=True)

    fear = fear_index(num_days_daily)

    for n, client in client_dict.items():
        table.add_column(f"{n}", style="yellow", justify="right")
        table.add_column("#", style="cyan", justify="left")

    dailydict = {}

    for n, cl in client_dict.items():
        t = cl.rest_client.daily(days=num_days_daily)
        for day in t["data"]:
            if day["date"] not in dailydict.keys():
                dailydict[day["date"]] = [
                    day["date"],
                    f"{fear[day['date']]}",
                    f"{round(float(day['abs_profit']),2)} {t['stake_currency']}",
                    f"{day['trade_count']}",
                ]
            else:
                dailydict[day["date"]].append(
                    f"{round(float(day['abs_profit']),2)} {t['stake_currency']}"
                )
                dailydict[day["date"]].append(f"{day['trade_count']}")

    for day, vals in dailydict.items():
        table.add_row(*vals)

    return table


# thanks @rextea!
def fear_index(num_days_daily, retfear={}):
    default_resp = {
        "name": "Fear and Greed Index",
        "data": [
            {
                "value": "3",
                "value_classification": "Neutral",
                "timestamp": str(datetime.today()),
            }
        ],
    }

    if not retfear:
        resp = requests.get(
            f"https://api.alternative.me/fng/?limit={num_days_daily}&date_format=kr"
        )
    else:
        if str(datetime.today()) in retfear:
            return retfear[str(datetime.today())]
        else:
            resp = requests.get("https://api.alternative.me/fng/?limit=1&date_format=kr")

    if resp is not None and resp.headers.get("Content-Type").startswith("application/json"):
        try:
            prev_resp = resp.json()
            df_gf = prev_resp["data"]
        except Exception:
            prev_resp = default_resp
            df_gf = prev_resp["data"]
    else:
        prev_resp = default_resp
        df_gf = prev_resp["data"]

    colourmap = {}
    colourmap["Extreme Fear"] = "[red]"
    colourmap["Fear"] = "[lightred]"
    colourmap["Neutral"] = "[yellow]"
    colourmap["Greed"] = "[lightgreen]"
    colourmap["Extreme Greed"] = "[green]"

    for i in df_gf:
        retfear[i["timestamp"]] = (
            f"{colourmap[i['value_classification']]}{i['value_classification']}"
        )

    return retfear


def dash_trades_summary(
    row_data,
    footer={"all_open_profit": "0", "num_wins_losses": "0/0", "all_total_profit": "0"},
    colours=FtuiColours(),
) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS, show_footer=True)

    # ("Bot", "# Trades", "Open Profit", "W/L", "Winrate", "Exp.", "Exp. Rate", "Med W", "Med L", "Tot. Profit")
    table.add_column("Bot", style=colours.bot_col, no_wrap=True)
    table.add_column("Start", style=colours.bot_start_col, no_wrap=True)
    table.add_column("# Trades", no_wrap=True)
    table.add_column("Open Profit", style="blue", justify="right", no_wrap=True)
    table.add_column("W/L", justify="right", no_wrap=True)
    table.add_column("Winrate", justify="right", no_wrap=True)
    table.add_column("Exp.", justify="right", no_wrap=True)
    table.add_column("Exp. Rate", justify="left", no_wrap=True)
    table.add_column("Med. W", justify="right", no_wrap=True)
    table.add_column("Med. L", justify="left", no_wrap=True)
    table.add_column("Tot. Profit", justify="right", no_wrap=True)

    for row in row_data:
        table.add_row(*row)

    table.columns[3].footer = footer["all_open_profit"]
    table.columns[4].footer = footer["num_wins_losses"]
    table.columns[10].footer = footer["all_total_profit"]

    return table


def dash_open_trades_table(row_data, trading_mode="spot", colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Bot", "ID", "Pair", "Open Rate", "Current Rate", "Stop %", "Profit %", "Profit", "Dur.", "S/L", "Entry")
    table.add_column("Bot", style=colours.bot_col, no_wrap=True)
    table.add_column("ID", style=colours.trade_id_col, no_wrap=True)
    table.add_column("Pair", style=colours.pair_col, no_wrap=True)
    table.add_column("Stake", justify="left")

    if trading_mode != "spot":
        table.add_column("Leverage", justify="left")

    table.add_column("# Orders", no_wrap=True)
    table.add_column("Open Rate", style=colours.open_rate_col, no_wrap=True)
    table.add_column("Rate", style=colours.current_rate_col, no_wrap=True)
    table.add_column("Stop %", no_wrap=True)
    table.add_column("Max. %", justify="left")
    table.add_column("Prof. %", justify="right")
    table.add_column("Prof.", justify="left")
    table.add_column("Dur.", justify="right")
    table.add_column("S/L", justify="center")
    table.add_column("Tag", justify="center")

    for row in row_data:
        table.add_row(*row)

    return table


def dash_closed_trades_table(row_data, colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Bot", "ID", "Pair", "Profit %", "Profit", "Dur.", "Exit")
    table.add_column("Bot", style=colours.bot_col, no_wrap=True)
    table.add_column("ID", style=colours.trade_id_col, no_wrap=True)
    table.add_column("Pair", style=colours.pair_col, no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Open Date", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("Enter", justify="left")
    table.add_column("Exit", justify="left")

    for row in row_data:
        table.add_row(*row)

    return table


def dash_cumulative_profit_plot_data(trades, bot_list=[], pair=None):
    if trades.shape[0] > 0 and bot_list:
        # Filter trades to what's in the bot_list
        trades = trades.loc[trades['Bot'].apply(lambda x: x in bot_list)].copy()

        # Filter trades to one pair
        if pair is not None:
            trades = trades.loc[trades["Pair"] == pair].copy()

    if trades.shape[0] > 0 and "Open Date" in trades.columns:
        s = trades.resample("D", on="Open Date")["Profit"].sum()
    
        data = pd.DataFrame(index=s.index, data={"binned": s.values})
        data["plot_cumprof"] = data["binned"].cumsum().round(2)
        data["plot_cumprof"].ffill(inplace=True)
    else:
        data = pd.DataFrame()

    return data


def bot_trades_summary_table(row_data, colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    table.add_column("Start", style=colours.bot_start_col, no_wrap=True)
    table.add_column("# Trades", no_wrap=True)
    table.add_column("Open Profit", style="blue", justify="right", no_wrap=True)
    table.add_column("W/L", justify="right", no_wrap=True)
    table.add_column("Winrate", justify="right", no_wrap=True)
    table.add_column("Exp.", justify="right", no_wrap=True)
    table.add_column("Exp. Rate", justify="right", no_wrap=True)
    table.add_column("Med. W", justify="right", no_wrap=True)
    table.add_column("Med. L", justify="right", no_wrap=True)
    table.add_column("Tot. Profit", justify="right", no_wrap=True)

    for row in row_data:
        table.add_row(*row)

    return table


def bot_open_trades_table(row_data, trading_mode="spot", colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("ID", "Pair", "Open Rate", "Current Rate", "Stop %", "Profit %", "Profit", "Dur.", "S/L", "Entry")
    table.add_column("ID", style=colours.trade_id_col, no_wrap=True)
    table.add_column("Pair", style=colours.pair_col, no_wrap=True)
    table.add_column("Stake", justify="left")

    if trading_mode != "spot":
        table.add_column("Leverage", justify="left")

    table.add_column("# Orders", no_wrap=True)
    table.add_column("Open Rate", style=colours.open_rate_col, no_wrap=True)
    table.add_column("Rate", style=colours.current_rate_col, no_wrap=True)
    table.add_column("Stop %", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("S/L", justify="center")
    table.add_column("Tag", justify="center")

    for row in row_data:
        table.add_row(*row)

    return table


def bot_closed_trades_table(row_data, trading_mode="spot", colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("ID", "Pair", "Profit %", "Profit", "Dur.", "Exit")
    table.add_column("ID", style=colours.trade_id_col, no_wrap=True)
    table.add_column("Pair", style=colours.pair_col, no_wrap=True)
    table.add_column("Stake", justify="left")

    if trading_mode != "spot":
        table.add_column("Leverage", justify="left")

    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Open Date", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("Enter", justify="left")
    table.add_column("Exit", justify="left")

    for row in row_data:
        table.add_row(*row)

    return table


def bot_tag_summary_table(row_data, colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Tag", "W/L", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit")
    table.add_column("Tag", style="white", no_wrap=True)
    table.add_column("W/L", style="purple", no_wrap=True)
    table.add_column("Avg Dur.", justify="right")
    table.add_column("Avg Win Dur.", justify="right")
    table.add_column("Avg Loss Dur.", justify="right")
    table.add_column("Profit", justify="right")

    for row in row_data:
        table.add_row(*row)

    return table


def bot_perf_summary_table(row_data, colours=FtuiColours()) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Pair", "# Trades", "Avg Profit %", "Total Profit"),
    table.add_column("Pair", style=colours.pair_col, no_wrap=True)
    table.add_column("# Trades", style="white", no_wrap=True)
    table.add_column("Avg Profit %", justify="right")
    table.add_column("Total Profit", justify="right")

    for row in row_data:
        table.add_row(*row)

    return table


def bot_general_info(client) -> str:
    config = client.get_client_config()

    general_text = (
        "## General"
        "\n\n"
        f"Running Freqtrade {config['version']}"
        "\n\n"
        f"Running with {config['max_open_trades']}x "
        f"{config['stake_amount']} {config['stake_currency']} "
        f"on {config['exchange']} in {config['trading_mode']} markets, "
        f"with Strategy {config['strategy']}."
        "\n\n"
        f"Stoploss on exchange is {'enabled' if config['stoploss_on_exchange'] else 'disabled'}."
        "\n\n"
        f"Currently running, force entry: {config['force_entry_enable']}"
        "\n\n"
        f"{config['runmode']}"
        "\n\n"
    )

    return general_text


def bot_general_metrics_table(client) -> str:
    config = client.get_client_config()

    t = client.get_total_profit()
    if t is None:
        return "[ERROR] Could not retrieve profit data."

    trade_count = t["trade_count"]

    profit_factor = round(t['profit_factor'], 2) if t['profit_factor'] is not None else "-"

    table = Table(expand=True, box=box.HORIZONTALS, row_styles=["grey89", ""])
    table.add_column("Metric", style="bold white", no_wrap=True, ratio=1)
    table.add_column("Value", style="white", no_wrap=False, ratio=2)

    row_data = [
        (
            "ROI closed trades",
            f"{round(t['profit_closed_coin'], 2)} {config['stake_currency']} "
            f"({chr(0x03BC)} {round(t['profit_closed_ratio_mean']*100, 2)}%) "
            f"(∑ {round(t['profit_all_ratio_sum']*100, 2)}%)",
        ),
        (
            "ROI all trades",
            f"{round(t['profit_all_coin'], 2)} {config['stake_currency']} "
            f"({chr(0x03BC)} {round(t['profit_all_ratio_mean']*100, 2)}%)",
        ),
        ("Total Trade count", f"{trade_count}"),
        ("Bot started", f"{t['bot_start_date']}"),
        ("First Trade opened", f"{t['first_trade_date']}"),
        ("Latest Trade opened", f"{t['latest_trade_date']}"),
        ("Win / Loss", f"{t['winning_trades']} / {t['losing_trades']}"),
        ("Winrate", f"{round(t['winrate']* 100, 3)}%"),
        ("Expectancy (ratio)", f"{round(t['expectancy'], 2)} ({round(t['expectancy_ratio'], 2)})"),
        ("Avg. Duration", f"{t['avg_duration']}"),
        ("Best performing", f"{t['best_pair']}: {t['best_rate']}%"),
        ("Trading volume", f"{round(t['trading_volume'], 2)} {config['stake_currency']}"),
        ("Profit factor", f"{profit_factor}"),
        (
            "Max Drawdown",
            f"{round(t['max_drawdown']*100, 2)}% "
            f"({round(t['max_drawdown_abs'], 2)} {config['stake_currency']}) "
            f"from {t['max_drawdown_start']} to {t['max_drawdown_end']}",
        ),
    ]

    for row in row_data:
        table.add_row(*row)

    return table


def bot_config(client) -> str:
    config = client.get_client_config()

    config_text = (
        "## Bot Info\n\n"
        f"**Bot Name**            : {config['bot_name']}  \n"
        f"**URL**                 : [{client.url}:{client.port}]({client.url}:{client.port})\n\n"
        f"**Version**             : {config['version']}  \n"
        f"**Runmode**             : {config['runmode']}  \n"
        f"**Force Entry**         : {config['force_entry_enable']}  \n"
        f"**Position Adjustment** : {config['position_adjustment_enable']}\n\n"
        f"## Strategy Info\n\n"
        f"**Strategy**            : {config['strategy']}  \n"
        f"**Strategy Version**    : {config['strategy_version']}  \n"
        f"**Timeframe**           : {config['timeframe']}  \n"
        f"**Stoploss**            : {config['stoploss']}  \n"
        f"**Max Open Trades**     : {config['max_open_trades']}\n\n"
        f"## Market Config\n\n"
        f"**Exchange**            : {config['exchange']}  \n"
        f"**Trading Mode**        : {config['trading_mode']}  \n"
        f"**Shorting**            : {config['short_allowed']}  \n"
        f"**Stake Currency**      : {config['stake_currency']}  \n"
        f"**Stake Amount**        : {config['stake_amount']}\n\n"
    )

    return config_text
