from datetime import datetime, timedelta
import requests

import numpy as np
import pandas as pd

from rich import box
from rich.table import Table
from rich.text import Text

from textual import log

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

# thanks @rextea!
def fear_index(num_days_daily, retfear = {}):
    default_resp = {
        "name": "Fear and Greed Index",
        "data": [
            {
                "value": "3",
                "value_classification": "Neutral",
                "timestamp": str(datetime.today()),
            }
        ]
    }

    if not retfear:
        resp = requests.get(f'https://api.alternative.me/fng/?limit={num_days_daily}&date_format=kr')
    else:
        if str(datetime.today()) in retfear:
            return retfear[str(datetime.today())]
        else:
            resp = requests.get('https://api.alternative.me/fng/?limit=1&date_format=kr')

    if resp is not None and resp.headers.get('Content-Type').startswith('application/json'):
        try:
            prev_resp = resp.json()
            df_gf = prev_resp['data']
        except:
            prev_resp = default_resp
            df_gf = prev_resp['data']
    else:
        prev_resp = default_resp
        df_gf = self.prev_resp['data']

    colourmap = {}
    colourmap['Extreme Fear'] = '[red]'
    colourmap['Fear'] = '[lightred]'
    colourmap['Neutral'] = '[yellow]'
    colourmap['Greed'] = '[lightgreen]'
    colourmap['Extreme Greed'] = '[green]'

    for i in df_gf:
        retfear[i['timestamp']] = f"{colourmap[i['value_classification']]}{i['value_classification']}"

    return retfear

def dash_all_bot_summary(row_data) -> Table:
    table = Table(expand=True, box=box.SIMPLE_HEAD)

    table.add_column("Open", style="white", justify="left", ratio=1, no_wrap=True)
    table.add_column("Closed", style="white", justify="left", ratio=1, no_wrap=True)
    table.add_column("Daily", style="white", justify="left", ratio=1, no_wrap=True)
    table.add_column("Weekly", style="white", justify="left", ratio=1, no_wrap=True)
    table.add_column("Monthly", style="white", justify="left", ratio=1, no_wrap=True)

    for row in row_data:
        table.add_row(
            *row
        )

    return table

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
        for day in t['data']:
            if day['date'] not in dailydict.keys():
                dailydict[day['date']] = [day['date'], f"{fear[day['date']]}", f"{round(float(day['abs_profit']),2)} {t['stake_currency']}", f"{day['trade_count']}"]
            else:
                dailydict[day['date']].append(f"{round(float(day['abs_profit']),2)} {t['stake_currency']}")
                dailydict[day['date']].append(f"{day['trade_count']}")

    for day, vals in dailydict.items():
        table.add_row(
            *vals
        )

    return table

def tradeinfo(client_dict, trades_dict, indicators) -> Table:
    yesterday = (datetime.now() - timedelta(days = 1)).strftime("%Y%m%d")

    table = Table(expand=True, box=box.HORIZONTALS)

    table.add_column("Pair", style="magenta", no_wrap=True, justify="left")
    table.add_column("Open", no_wrap=True, justify="right")
    table.add_column("Close", no_wrap=True, justify="right")
    table.add_column("Volume", no_wrap=True, justify="right")

    for ind in indicators:
        header_name = ind['headername']
        table.add_column(header_name, style="cyan", no_wrap=True, justify="left")

    shown_pairs = []

    for n, client in client_dict.items():
        cl = client[0]
        state = client[1]

        uparrow = "\u2191"
        downarrow = "\u2193"

        if isinstance(cl, ftrc.FtRestClient):
            if state == "running":
                open_trades = cl.status()
                if open_trades is not None:
                    for t in open_trades:
                        if t['pair'] not in shown_pairs:
                            try:
                                pairjson = cl.pair_candles(t['pair'], "5m", 2)
                                shown_pairs.append(t['pair'])

                                if pairjson['columns'] and pairjson['data']:
                                    cols = pairjson['columns']
                                    data = pairjson['data']

                                    pairdf = pd.DataFrame(data, columns=cols)
                                    op = pairdf['open'].values[0]
                                    cl = pairdf['close'].values[0]
                                    candle_colour = "[green]"
                                    if op >= cl:
                                        candle_colour = "[red]"

                                    inds = []

                                    inds.append(f"{t['pair']}")
                                    inds.append(f"{candle_colour}{round(op, 3)}")
                                    inds.append(f"{candle_colour}{round(cl, 3)}")
                                    inds.append(f"{int(pairdf['volume'].values[0])}")

                                    for ind in indicators:
                                        df_colname = str(ind['colname'])
                                        round_val = ind['round_val']
                                        if df_colname in pairdf:
                                            curr_ind = pairdf[df_colname].values[0]
                                            prev_ind = pairdf[df_colname].values[1]

                                            trend = ""
                                            if prev_ind > curr_ind:
                                                trend = f"[red]{downarrow} "
                                            elif prev_ind < curr_ind:
                                                trend = f"[green]{uparrow} "
                                            else:
                                                trend = "[cyan]- "

                                            if round_val == 0:
                                                dval = int(curr_ind)
                                            else:
                                                dval = round(curr_ind, round_val)
                                            inds.append(f"{trend}[white]{dval}")
                                        else:
                                            inds.append("")

                                    table.add_row(
                                        *inds
                                    )
                                    # tc = get_trade_candle(pairdf, t['open_date'], t['pair'], "5m")
                            except Exception as e:
                                ## noone likes exceptions
                                #print(e)
                                pass

            closed_trades = trades_dict[n]
            do_stuff = True
            if closed_trades is not None and do_stuff == True:
                t = closed_trades[0]

                if t['pair'] not in shown_pairs:
                    try:
                        pairjson = cl.pair_candles(t['pair'], "5m", 2)
                        shown_pairs.append(t['pair'])

                        if pairjson['columns'] and pairjson['data']:
                            cols = pairjson['columns']
                            data = pairjson['data']

                            pairdf = pd.DataFrame(data, columns=cols)
                            op = pairdf['open'].values[0]
                            cl = pairdf['close'].values[0]
                            candle_colour = "[green]"
                            if op >= cl:
                                candle_colour = "[red]"

                            inds = []
                            inds.append(f"{t['pair']}")
                            inds.append(f"{candle_colour}{round(op, 3)}")
                            inds.append(f"{candle_colour}{round(cl, 3)}")
                            inds.append(f"{int(pairdf['volume'].values[0])}")

                            for ind in indicators:
                                df_colname = str(ind['colname'])
                                round_val = ind['round_val']
                                if df_colname in pairdf:
                                    curr_ind = pairdf[df_colname].values[0]
                                    prev_ind = pairdf[df_colname].values[1]

                                    trend = ""
                                    if prev_ind > curr_ind:
                                        trend = f"[red]{downarrow} "
                                    elif prev_ind < curr_ind:
                                        trend = f"[green]{uparrow} "
                                    else:
                                        trend = "[cyan]- "

                                    if round_val == 0:
                                        dval = int(curr_ind)
                                    else:
                                        dval = round(curr_ind, round_val)
                                    inds.append(f"{trend}[white]{dval}")
                                else:
                                    inds.append("")

                            table.add_row(
                                *inds
                            )
                    except Exception as e:
                        ## noone likes exceptions
                        #print(e)
                        pass

    return table

def dash_trades_summary(row_data, footer={"all_open_profit":"0", "num_wins_losses": "0/0", "all_total_profit": "0"}) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS, show_footer=True)

    # ("Bot", "# Trades", "Open Profit", "W/L", "Winrate", "Exp.", "Exp. Rate", "Med W", "Med L", "Tot. Profit")
    table.add_column("Bot", style="yellow", no_wrap=True)
    table.add_column("Start", style="white", no_wrap=True)
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
        table.add_row(
            *row
        )

    table.columns[3].footer = footer["all_open_profit"]
    table.columns[4].footer = footer["num_wins_losses"]
    table.columns[10].footer = footer["all_total_profit"]

    return table


def dash_open_trades_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Bot", "ID", "Pair", "Open Rate", "Current Rate", "Stop %", "Profit %", "Profit", "Dur.", "S/L", "Entry")
    table.add_column("Bot", style="yellow", no_wrap=True)
    table.add_column("ID", style="white", no_wrap=True)
    table.add_column("Pair", style="magenta", no_wrap=True)
    table.add_column("Open Rate", style="white", no_wrap=True)
    table.add_column("Rate", style="white", no_wrap=True)
    table.add_column("Stop %", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("S/L", justify="center")
    table.add_column("Tag", justify="center")

    for row in row_data:
        table.add_row(
            *row
        )

    return table


def dash_closed_trades_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Bot", "ID", "Pair", "Profit %", "Profit", "Dur.", "Exit")
    table.add_column("Bot", style="yellow", no_wrap=True)
    table.add_column("ID", style="white", no_wrap=True)
    table.add_column("Pair", style="magenta", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Open Date", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("Enter", justify="left")
    table.add_column("Exit", justify="left")

    for row in row_data:
        table.add_row(
            *row
        )

    return table

def dash_cumulative_profit_plot_data(trades, bot=None, pair=None):
    if trades.shape[0] > 0 and bot is not None:
        # Filter trades to one bot
        trades = trades.loc[trades['Bot'] == bot].copy()

        # Filter trades to one pair
        if pair is not None:
            trades = trades.loc[trades['Pair'] == pair].copy()

    s = trades.resample('D', on='Open Date')['Profit'].sum()

    data = pd.DataFrame(index=s.index, data={'binned': s.values})
    data['plot_cumprof'] = data['binned'].cumsum().round(2)
    data['plot_cumprof'].ffill(inplace=True)

    return data


def bot_trades_summary_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    table.add_column("Start", style="white", no_wrap=True)
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
        table.add_row(
            *row
        )

    return table

def bot_open_trades_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("ID", "Pair", "Open Rate", "Current Rate", "Stop %", "Profit %", "Profit", "Dur.", "S/L", "Entry")
    table.add_column("ID", style="white", no_wrap=True)
    table.add_column("Pair", style="magenta", no_wrap=True)
    table.add_column("Open Rate", style="white", no_wrap=True)
    table.add_column("Rate", style="white", no_wrap=True)
    table.add_column("Stop %", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("S/L", justify="center")
    table.add_column("Tag", justify="center")

    for row in row_data:
        table.add_row(
            *row
        )

    return table


def bot_closed_trades_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("ID", "Pair", "Profit %", "Profit", "Dur.", "Exit")
    table.add_column("ID", style="white", no_wrap=True)
    table.add_column("Pair", style="magenta", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Open Date", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("Enter", justify="left")
    table.add_column("Exit", justify="left")

    for row in row_data:
        table.add_row(
            *row
        )

    return table


def bot_tag_summary_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Tag", "W/L", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit")
    table.add_column("Tag", style="white", no_wrap=True)
    table.add_column("W/L", style="magenta", no_wrap=True)
    table.add_column("Avg Dur.", justify="right")
    table.add_column("Avg Win Dur.", justify="right")
    table.add_column("Avg Loss Dur.", justify="right")
    table.add_column("Profit", justify="right")

    for row in row_data:
        table.add_row(
            *row
        )

    return table

def bot_perf_summary_table(row_data) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)

    # ("Pair", "# Trades", "Avg Profit %", "Total Profit"),
    table.add_column("Pair", style="white", no_wrap=True)
    table.add_column("# Trades", style="magenta", no_wrap=True)
    table.add_column("Avg Profit %", justify="right")
    table.add_column("Total Profit", justify="right")

    for row in row_data:
        table.add_row(
            *row
        )

    return table

def bot_config(config) -> str:
    config_text = f"""
    [italic]Bot Info[/italic]
    [bold]Bot Name            :[/bold] {config['bot_name']}
    [bold]Version             :[/bold] {config['version']}
    [bold]Runmode             :[/bold] {config['runmode']}
    [bold]Force Entry         :[/bold] {config['force_entry_enable']}
    [bold]Position Adjustment :[/bold] {config['position_adjustment_enable']}

    [italic]Strategy Info[/italic]
    [bold]Strategy            :[/bold] {config['strategy']}
    [bold]Strategy Version    :[/bold] {config['strategy_version']}
    [bold]Timeframe           :[/bold] {config['timeframe']}
    [bold]Stoploss            :[/bold] {config['stoploss']}
    [bold]Max Open Trades     :[/bold] {config['max_open_trades']}

    [italic]Market Config[/italic]
    [bold]Exchange            :[/bold] {config['exchange']}
    [bold]Trading Mode        :[/bold] {config['trading_mode']}
    [bold]Shorting            :[/bold] {config['short_allowed']}
    [bold]Stake Currency      :[/bold] {config['stake_currency']}
    [bold]Stake Amount        :[/bold] {config['stake_amount']}
    """

    return config_text