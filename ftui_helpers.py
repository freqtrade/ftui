from datetime import datetime, timezone, timedelta
import requests

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.prompt import Prompt, IntPrompt
from rich.spinner import Spinner
from rich.status import Status
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.rule import Rule


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

def closed_trades_table(client_dict, num_closed_trades) -> Table:
    table = Table(expand=True, box=box.HORIZONTALS)
    
    table.add_column("ID", style="white", no_wrap=True)
    table.add_column("Bot", style="yellow", no_wrap=True)
    table.add_column("Strat", style="cyan")
    table.add_column("Pair", style="magenta", no_wrap=True)
    table.add_column("Profit %", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Dur.", justify="right")
    table.add_column("Exit", justify="right")
    
    fmt = "%Y-%m-%d %H:%M:%S"
    
    for n, cl in client_dict.items():
        trades = cl.get_all_closed_trades()
        if trades is not None:
            for t in trades[:num_closed_trades]:
                otime = datetime.strptime(t['open_date'], fmt).astimezone(tz=timezone.utc)
                ctime = datetime.strptime(t['close_date'], fmt).astimezone(tz=timezone.utc)
                rpfta = round(float(t['profit_abs']), 2)

                table.add_row(
                    f"{t['trade_id']}",
                    f"{n}",
                    f"{t['strategy']}",
                    f"{t['pair']}",
                    f"[red]{t['profit_pct']}" if t['profit_pct'] <= 0 else f"[green]{t['profit_pct']}",
                    f"[red]{rpfta}" if rpfta <= 0 else f"[green]{rpfta}",
                    f"{str(ctime-otime).split('.')[0]}",
                    f"{t['exit_reason']}"
                )

    return table

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