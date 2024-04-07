from datetime import datetime, timezone

from rich.table import Table
from rich.text import Text

from textual import work, on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen, ModalScreen
from textual.worker import get_current_worker

from textual.widgets import (
    Collapsible, DataTable, Digits,
    Footer, Header, Label, ListView, ListItem,
    Log, Markdown, Select, Static, TabbedContent,
    TabPane
)

import pandas as pd
import numpy as np
import subprocess

from textual_plotext import PlotextPlot

import ftui.ftui_client as ftuic
import ftui.ftui_helpers as fth


class DashboardScreen(Screen):

    timers = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="above"):
            with Container(id="all-open-profit"):
                yield Label("Open")
                yield Digits(
                    id="all-bot-summary-open-profit"
                )

            with Container(id="all-closed-profit"):
                yield Label("Closed")
                yield Digits(
                    id="all-bot-summary-closed-profit"
                )

            with Container(id="all-daily-profit"):
                yield Label("Daily")
                yield Digits(
                    id="all-bot-summary-daily-profit"
                )
                yield Static(id="yesterday-profit")

            with Container(id="all-weekly-profit"):
                yield Label("Weekly")
                yield Digits(
                    id="all-bot-summary-weekly-profit"
                )
                yield Static(id="last-week-profit")

            with Container(id="all-monthly-profit"):
                yield Label("Monthly")
                yield Digits(
                    id="all-bot-summary-monthly-profit"
                )
                yield Static(id="last-month-profit")

        with Container(id="parent-container"):
            with Container(id="dash-container"):
                with Container(id="dash-all-trade-summary"):
                    yield Static(
                        id="all-trade-summary-table"
                    )

                with Container(id="dash-collapsibles"):
                    with Collapsible(title="All Open Trades", id="dsh-op-collap", collapsed=False):
                        yield Static(
                            id="all-open-trades-table",
                            classes="bg-static-default"
                        )

                    with Collapsible(title="All Closed Trades", id="dsh-cl-collap", collapsed=True):
                        yield Static(
                            id="dash-closed-profit",
                            classes="bg-static-default"
                        )

                    with Collapsible(title="Cumulative Profit", id="dsh-cp-collap", collapsed=True):
                        yield PlotextPlot(
                            id="dash-cumprof-profit"
                        )

                    # with Collapsible(title="Daily Trade Summary", id="dsh-dt-collap", collapsed=True):
                    #     yield Static(
                    #         id="dash-daily-profit"
                    #     )

        yield Footer()

    def on_mount(self) -> None:
        ats = self.query_one("#dash-all-trade-summary")
        ats.loading = True

        summary_digits = self.query_one("#above").query(Digits)
        for sd in summary_digits:
            sd.loading = True

        update_one_sec_render = self.set_interval(
            1, self.update_per_sec
        )
        self.timers["1sec"] = update_one_sec_render

        update_five_sec_render = self.set_interval(
            5, self.update_per_five_sec
        )
        self.timers["5sec"] = update_five_sec_render


    async def update_per_sec(self):
        self.update_dashboard_all_bot_summary()

        dsh_op_collap = self.query_one("#dsh-op-collap")
        if dsh_op_collap.collapsed is False:
            self.update_dashboard_all_open_trades()

    async def update_per_five_sec(self):
        self.update_dashboard_all_trade_summary()

        dsh_cl_collap = self.query_one("#dsh-cl-collap")
        if dsh_cl_collap.collapsed is False:
            self.update_dashboard_all_closed_trades()

        dsh_cp_collap = self.query_one("#dsh-cp-collap")
        if dsh_cp_collap.collapsed is False:
            self.update_cumulative_profit_plot()

    def _render_open_trade_data(self, data):
        row_data = []

        for idx, v in data.iterrows():
            bot_name = v['Bot']
            row_data.append((
                f"[@click=app.switch_to_bot('{bot_name}')]{bot_name}[/]",
                f"{v['ID']}",
                f"{v['Pair']}",
                f"{v['Open Rate']}",
                f"{v['Current Rate']}",
                fth.red_or_green(float(v['Stop %'])),
                fth.red_or_green(float(v['Profit %']), justify='right'),
                fth.red_or_green(float(v['Profit']), justify='right'),
                str(v["Dur."]).split('.')[0].replace('0 days ', ''),
                f"{v['S/L']}",
                f"{v['Entry']}",
            ))

        return row_data

    def _render_closed_trade_data(self, data):
        row_data = []
        data = data.sort_values(by='Close Date', ascending=False)

        for idx, v in data.iterrows():
            row_data.append((
                f"{v['Bot']}",
                f"{v['ID']}",
                f"{v['Pair']}",
                fth.red_or_green(float(v['Profit %']), justify='right'),
                fth.red_or_green(float(v['Profit']), justify='right'),
                f"[cyan]{str(v['Open Date']).split('+')[0]}",
                str(v['Dur.']).split('.')[0].replace('0 days ', ''),
                f"{v['Entry']}",
                f"{v['Exit']}",
            ))

        return row_data

    @work(group="dash_all_summary_worker", exclusive=True, thread=True)
    def update_dashboard_all_bot_summary(self):
        closed_profit = 0
        open_profit = 0
        daily_profit = 0
        yesterday_profit = 0
        weekly_profit = 0
        last_week_profit = 0
        monthly_profit = 0
        last_month_profit = 0

        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        for n, cl in client_dict.items():
            open_data = client_dfs[cl.name]['op_data'].copy() if cl.name in client_dfs and 'op_data' in client_dfs[cl.name] else pd.DataFrame()
            closed_data = client_dfs[cl.name]['cl_data'].copy() if cl.name in client_dfs and 'cl_data' in client_dfs[cl.name] else pd.DataFrame()

            tot_profit = 0
            if not open_data.empty:
                tot_profit = round(open_data['Profit'].sum(), 2)

            #t = cl.get_total_profit()
            pcc = 0
            if not closed_data.empty:
                pcc = round(closed_data['Profit'].sum(), 2)

            closed_profit = closed_profit + pcc
            open_profit = open_profit + tot_profit

            d = cl.get_daily_profit(days=2)
            if d is not None and "data" in d and d['data']:
                daily_profit = daily_profit + d['data'][0]['abs_profit']
                yesterday_profit = d['data'][1]['abs_profit']
            w = cl.get_weekly_profit(weeks=2)
            if w is not None and "data" in w and w['data']:
                weekly_profit = weekly_profit + w['data'][0]['abs_profit']
                last_week_profit = w['data'][1]['abs_profit']
            m = cl.get_monthly_profit(months=2)
            if m is not None and "data" in m and m['data']:
                monthly_profit = monthly_profit + m['data'][0]['abs_profit']
                last_month_profit = m['data'][1]['abs_profit']

        cps = round(closed_profit, 2)
        ops = round(open_profit, 2)
        dps = round(daily_profit, 2)
        wps = round(weekly_profit, 2)
        mps = round(monthly_profit, 2)

        opsd = self.query_one("#all-bot-summary-open-profit")
        cpsd = self.query_one("#all-bot-summary-closed-profit")
        dpsd = self.query_one("#all-bot-summary-daily-profit")
        wpsd = self.query_one("#all-bot-summary-weekly-profit")
        mpsd = self.query_one("#all-bot-summary-monthly-profit")
        ypsd = self.query_one("#yesterday-profit")
        lwpsd = self.query_one("#last-week-profit")
        lmpsd = self.query_one("#last-month-profit")

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(opsd.update, f"{ops}")
            self.app.call_from_thread(cpsd.update, f"{cps}")
            self.app.call_from_thread(dpsd.update, f"{dps}")
            self.app.call_from_thread(wpsd.update, f"{wps}")
            self.app.call_from_thread(mpsd.update, f"{mps}")
            self.app.call_from_thread(ypsd.update, Text(f"{round(yesterday_profit, 2)}", justify="center"))
            self.app.call_from_thread(lwpsd.update, Text(f"{round(last_week_profit, 2)}", justify="center"))
            self.app.call_from_thread(lmpsd.update, Text(f"{round(last_month_profit, 2)}", justify="center"))

        fth.set_red_green_widget_colour(opsd, ops)
        fth.set_red_green_widget_colour(cpsd, cps)
        fth.set_red_green_widget_colour(dpsd, dps)
        fth.set_red_green_widget_colour(ypsd, yesterday_profit)
        fth.set_red_green_widget_colour(wpsd, wps)
        fth.set_red_green_widget_colour(lwpsd, last_week_profit)
        fth.set_red_green_widget_colour(mpsd, mps)
        fth.set_red_green_widget_colour(lmpsd, last_month_profit)

        opsd.loading = False
        cpsd.loading = False
        dpsd.loading = False
        wpsd.loading = False
        mpsd.loading = False


    @work(group="dash_all_open_worker", exclusive=True, thread=True)
    def update_dashboard_all_open_trades(self):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        all_open_df = pd.DataFrame()
        for n, cl in client_dict.items():
            if cl.name in client_dfs and 'op_data' in client_dfs[cl.name]:
                data = client_dfs[cl.name]['op_data'].copy()
                if not data.empty:
                    all_open_df = pd.concat([all_open_df, data])

        row_data = self._render_open_trade_data(all_open_df)

        dt = self.query_one("#all-open-trades-table")
        table = fth.dash_open_trades_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="dash_all_closed_worker", exclusive=True, thread=True)
    def update_dashboard_all_closed_trades(self, num_closed_trades=3) -> Table:
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        all_closed_df = pd.DataFrame()
        for n, cl in client_dict.items():
            if cl.name in client_dfs and 'cl_data' in client_dfs[cl.name]:
                data = client_dfs[cl.name]['cl_data'].copy()
                all_closed_df = pd.concat([all_closed_df, data[:num_closed_trades]])

        row_data = self._render_closed_trade_data(all_closed_df)

        dt = self.query_one("#dash-closed-profit")
        table = fth.dash_closed_trades_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="dash_all_trade_worker", exclusive=False, thread=True)
    def update_dashboard_all_trade_summary(self):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        row_data = [
            # ("Bot", "# Trades", "Open Profit", "W/L", "Winrate", "Exp.", "Exp. Rate", "Med W", "Med L", "Tot. Profit"),
        ]
        all_open_profit = 0
        all_profit = 0
        all_wins = 0
        all_losses = 0

        for n, cl in client_dict.items():
            open_data = client_dfs[cl.name]['op_data'].copy() if cl.name in client_dfs and 'op_data' in client_dfs[cl.name] else pd.DataFrame()
            closed_data = client_dfs[cl.name]['cl_data'].copy() if cl.name in client_dfs and 'cl_data' in client_dfs[cl.name] else pd.DataFrame()

            open_profit = 0
            mean_prof = 0
            mean_prof_w = 0
            mean_prof_l = 0
            median_win = 0
            median_loss = 0

            tp = 0
            tpw = []
            tpl = []

            if not open_data.empty:
                open_profit = round(open_data['Profit'].sum(), 2)

            if 'Profit' in closed_data.columns:
                tp = closed_data['Profit'].sum()

                tpw = closed_data.loc[closed_data['Profit'] >= 0, 'Profit']
                tpl = closed_data.loc[closed_data['Profit'] < 0, 'Profit']

                mean_prof = round(closed_data['Profit'].mean(), 2)

            if len(tpw) > 0:
                mean_prof_w = round(tpw.mean(), 2)
                median_win = round(tpw.median(), 2)

            if len(tpl) > 0:
                mean_prof_l = round(tpl.mean(), 2)
                median_loss = round(tpl.median(), 2)

            if (len(tpw) == 0) and (len(tpl) == 0):
                winrate = 0
                loserate = 0
            else:
                winrate = (len(tpw) / (len(tpw) + len(tpl))) * 100
                loserate = 100 - winrate

            expectancy_ratio = float('inf')
            if abs(mean_prof_l) > 0:
                expectancy_ratio = ((1 + (mean_prof_w / abs(mean_prof_l))) * (winrate / 100)) - 1

            expectancy = ((winrate/100) * mean_prof_w) - ((loserate/100) * mean_prof_l)

            t = cl.get_total_profit()
            if t is None:
                return []

            pcc = round(float(t['profit_closed_coin']), 2)
            # coin = stake_coin
            # coin = t['best_pair'].split('/')[1]
            bot_start_date = datetime.strptime(f"{t['bot_start_date']}+00:00", self.app.TZFMT).date()

            all_open_profit = all_open_profit + open_profit
            all_profit = all_profit + pcc
            all_wins = all_wins + t['winning_trades']
            all_losses = all_losses + t['losing_trades']

            row_data.append((
                f"{n}",
                f"{bot_start_date}",
                f"[cyan]{int(t['trade_count'])-int(t['closed_trade_count'])}[white]/[magenta]{t['closed_trade_count']}",
                fth.red_or_green(round(open_profit, 2)),
                f"[green]{t['winning_trades']}/[red]{t['losing_trades']}",
                f"[cyan]{round(winrate, 1)}",
                f"[magenta]{round(expectancy, 2)}",
                fth.red_or_green(round(expectancy_ratio, 2)),
                f"[green]{median_win}",
                f"[red]{median_loss}",
                fth.red_or_green(pcc, justify="right")
            ))

        footer = {
            "all_open_profit": fth.red_or_green(round(all_open_profit, 2)),
            "num_wins_losses": f"[green]{all_wins}/[red]{all_losses}",
            "all_total_profit": fth.red_or_green(round(all_profit, 2), justify="right")
        }

        dt = self.query_one("#all-trade-summary-table")
        table = fth.dash_trades_summary(row_data, footer)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)

        ats = self.query_one("#dash-all-trade-summary")
        ats.loading = False

    @work(group="dash_chart_worker", exclusive=True, thread=True)
    def update_cumulative_profit_plot(self):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        all_cum_data = pd.DataFrame()
        if 'all_closed' in client_dfs:
            all_cum_data = fth.dash_cumulative_profit_plot_data(client_dfs['all_closed'])

            if 'plot_cumprof' in all_cum_data.columns:
                chart_container = self.query_one("#dash-cumprof-profit")
                cplt = chart_container.plt
                dfmt = "Y-m-d"
                cplt.date_form(dfmt)

                all_cum_data.index = all_cum_data.index.tz_localize(None)

                dates = cplt.datetimes_to_string(all_cum_data.index)

                cplt.plot(dates, all_cum_data['plot_cumprof'].values)
                cplt.ylim(all_cum_data['plot_cumprof'].min() * 0.99, all_cum_data['plot_cumprof'].max() * 1.01)
                cplt.ylabel("Profit")

                worker = get_current_worker()
                if not worker.is_cancelled:
                    self.app.call_from_thread(chart_container.refresh)

class MainBotScreen(Screen):

    timers = {}

    TAB_FUNC_MAP = {
        ## tabs
        "open-trades-tab":"update_open_trades_tab",
        "closed-trades-tab":"update_closed_trades_tab",
        "tag-summary-tab":"update_tag_summary_tab",
        "perf-summary-tab":"update_performance_tab",
        "config-tab":"update_config_tab",
        "logs-tab":"update_logs_tab",
    }

    COLLAP_FUNC_MAP = {
        ##collapsibles
        "bot-chrt-collap":"update_chart_container",
    }

    client_select_options = [("Select Bot Client...", "Select.BLANK")]
    prev_chart_pair = None
    chart_data = {}

    ## LAYOUT
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="above-bot"):
            yield Select(options=self.client_select_options, allow_blank=False, id="client-select")

        with Container(id="parent-container"):
            with Container(id="right"):
                with Container(id="trades-summary"):
                    yield Static("Select a bot from the client list...", id="sel-bot-title")
                    yield Static(
                        id="trades-summary-table",
                        classes="bg-static-default"
                    )

                with Container(id="bot-chart-container"):
                    with Collapsible(title="Candlestick Chart", id="bot-chrt-collap", collapsed=False):
                        yield ListView(
                            id="whitelist",
                            classes="bg-static-default"
                        )
                        yield PlotextPlot(
                            id="bot-chart",
                            classes="bg-static-default"
                        )

                with TabbedContent(initial="open-trades-tab"):

                    with TabPane("Open Trades", id="open-trades-tab"):
                        yield Static(
                            id="open-trades-table",
                            classes="bg-static-default"
                        )

                    with TabPane("Closed Trades", id="closed-trades-tab"):
                        yield Static(
                            id="closed-trades-table",
                            classes="bg-static-default"
                        )

                    with TabPane("Tag Summary", id="tag-summary-tab"):
                        yield Static(
                            id="tag-summary-table",
                            classes="bg-static-default"
                        )

                    with TabPane("Performance", id="perf-summary-tab"):
                        yield Static(
                            id="perf-summary-table",
                            classes="bg-static-default"
                        )

                    with TabPane("Config", id="config-tab"):
                        yield Static(
                            id="config-summary",
                            classes="bg-static-default"
                        )

                    with TabPane("Logs", id="logs-tab"):
                        yield Log(id="log") #, wrap=True)
                        # yield Container(id="sysinfo-panel")

                    with TabPane("Debug", id="debug-tab"):
                        yield Log(id="debug-log")

        yield Footer()


    ## MOUNT AND TIMERS
    def on_mount(self) -> None:
        self.update_select_options()

        update_one_sec_render = self.set_interval(
            1, self.update_per_sec
        )
        self.timers["1sec"] = update_one_sec_render

        update_five_sec_render = self.set_interval(
            5, self.update_per_five_sec
        )
        self.timers["5sec"] = update_five_sec_render

        update_one_min_render = self.set_interval(
            60, self.update_per_one_min
        )
        self.timers["1min"] = update_one_min_render

    async def update_per_sec(self):
        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != 'Select.BLANK':
            self.update_trades_summary(bot_id)

            tab_id = self._get_active_tab_id()
            if tab_id == "open-trades-tab":
                self.update_open_trades_tab("open-trades-tab", bot_id)

    async def update_per_five_sec(self):
        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != 'Select.BLANK':
            tab_id = self._get_active_tab_id()
            if tab_id != "open-trades-tab" and tab_id in self.TAB_FUNC_MAP:
                getattr(self, self.TAB_FUNC_MAP[tab_id])(tab_id, bot_id)
        # else:
        #     self.update_select_options()

    async def update_per_one_min(self):
        bot_id = self._get_bot_id_from_client_list()
        if bot_id is not None and bot_id != 'Select.BLANK':
            self.update_chart(bot_id, pair=self.prev_chart_pair)
            self.update_whitelist(bot_id)


    ## TAB EVENT STUFF
    def _get_bot_id_from_client_list(self):
        try:
            sel = self.query_one("#client-select")
            bot_id = str(sel.value)
            return bot_id
        except:
            return None

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.tab.id
        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != 'Select.BLANK':
            if tab_id in self.TAB_FUNC_MAP:
                getattr(self, self.TAB_FUNC_MAP[tab_id])(tab_id, bot_id)

    def tab_select_func(self, tab_id, bot_id):
        if tab_id in self.TAB_FUNC_MAP:
            getattr(self, self.TAB_FUNC_MAP[tab_id])(tab_id, bot_id)

    def _get_active_tab_id(self):
        try:
            cont = self.query_one("#right")
            active_tab_id = cont.get_child_by_type(TabbedContent).active
            return active_tab_id
        except:
            return "open-trades-tab"

    def _get_tab(self, tab_id):
        return next(self.query(f"#{tab_id}").results(TabPane))

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        event.stop()

        active_tab_id = self._get_active_tab_id()
        bot_id = str(event.value)

        if bot_id != 'Select.BLANK':
            # self.update_select_options(bot_id=bot_id)

            self.query_one("#sel-bot-title").update(bot_id)
            self.update_trades_summary(bot_id)

            # update all tabs when select changed
            for tab in self.TAB_FUNC_MAP.keys():
                self.update_tab(tab, bot_id)

            self.update_whitelist(bot_id)
            self.update_chart(bot_id)

    @work(group="selswitch_workers", exclusive=True, thread=True)
    def update_select_options(self, bot_id=None):
        client_dict = self.app.client_dict

        options = []

        for name, cl in client_dict.items():
            ot, mt = cl.get_open_trade_count()
            options.append((f"{name} : {ot}/{mt} active trades", name))

        self.client_select_options = options

        sel = self.query_one("#client-select")
        sel.set_options(self.client_select_options)

        if bot_id is not None:
            sel.value = bot_id

    @work(group="tabswitch_workers", exclusive=False, thread=True)
    def update_tab(self, tab_id, bot_id):
        if bot_id is not None and bot_id != "None":
            self.tab_select_func(tab_id, bot_id)

    def update_chart_container(self, bot_id):
        bot_chrt_collap = self.query_one("#bot-chrt-collap")
        if bot_chrt_collap.collapsed is False:
            self.update_chart(bot_id, pair=self.prev_chart_pair)
            self.update_whitelist(bot_id)

    def update_screen(self, bot_id):
        self.update_trades_summary(bot_id)

        self.update_select_options(bot_id=bot_id)

        # update all tabs when bot selected from dashboard
        for tab in self.TAB_FUNC_MAP.keys():
            self.update_tab(tab, bot_id)

        self.update_chart_container(bot_id)

    ## bot trade summary
    @work(group="bot_summary_worker", exclusive=True, thread=True)
    def update_trades_summary(self, bot_id):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        cl = client_dict[bot_id]
        open_data = client_dfs[cl.name]['op_data'].copy() if cl.name in client_dfs and 'op_data' in client_dfs[cl.name] else pd.DataFrame()
        closed_data = client_dfs[cl.name]['cl_data'].copy() if cl.name in client_dfs and 'cl_data' in client_dfs[cl.name] else pd.DataFrame()

        self._render_trades_summary(cl, open_data, closed_data)

    def _render_trades_summary(self, cl, open_data, closed_data):
        row_data = [
            # ("Bot Start", "# Trades", "Open Profit", "W/L", "Winrate", "Exp.",
            #  "Exp. Rate", "Med. W", "Med. L", "Total"),
        ]

        open_profit = 0
        mean_prof = 0
        mean_prof_w = 0
        mean_prof_l = 0
        median_win = 0
        median_loss = 0

        tp = 0
        tpw = []
        tpl = []

        open_profit = 0

        if not open_data.empty:
            open_profit = round(open_data['Profit'].sum(), 2)

        if 'Profit' in closed_data.columns:
            tp = round(closed_data['Profit'].sum(), 2)

            tpw = closed_data.loc[closed_data['Profit'] >= 0, 'Profit']
            tpl = closed_data.loc[closed_data['Profit'] < 0, 'Profit']

            mean_prof = round(closed_data['Profit'].mean(), 2)

        if len(tpw) > 0:
            mean_prof_w = round(tpw.mean(), 2)
            median_win = round(tpw.median(), 2)

        if len(tpl) > 0:
            mean_prof_l = round(tpl.mean(), 2)
            median_loss = round(tpl.median(), 2)

        if (len(tpw) == 0) and (len(tpl) == 0):
            winrate = 0
            loserate = 0
        else:
            winrate = (len(tpw) / (len(tpw) + len(tpl))) * 100
            loserate = 100 - winrate

        expectancy_ratio = float('inf')
        if abs(mean_prof_l) > 0:
            expectancy_ratio = ((1 + (mean_prof_w / abs(mean_prof_l))) * (winrate / 100)) - 1

        expectancy = ((winrate/100) * mean_prof_w) - ((loserate/100) * mean_prof_l)

        t = cl.get_total_profit()
        if t is None:
            return []

        pcc = round(float(t['profit_closed_coin']), 2)
        # coin = stake_coin
        # coin = t['best_pair'].split('/')[1]
        bot_start_date = datetime.strptime(f"{t['bot_start_date']}+00:00", self.app.TZFMT).date()

        row_data.append((
            f"{bot_start_date}",
            f"[cyan]{int(t['trade_count'])-int(t['closed_trade_count'])}[white]/[magenta]{t['closed_trade_count']}",
            fth.red_or_green(round(open_profit, 2)),
            f"[green]{t['winning_trades']}/[red]{t['losing_trades']}",
            f"[cyan]{round(winrate, 1)}",
            f"[magenta]{round(expectancy, 2)}",
            fth.red_or_green(round(expectancy_ratio, 2)),
            f"[green]{median_win}",
            f"[red]{median_loss}",
            fth.red_or_green(pcc, justify="right")
        ))

        dt = self.query_one("#trades-summary-table")
        table = fth.bot_trades_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)

        dt.loading = False


    ## bot open trades tab
    @work(group="bot_open_trades_worker", exclusive=True, thread=True)
    def update_open_trades_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]

        tab = self._get_tab(tab_id)
        self._render_open_trade_summary(cl)

    def _render_open_trade_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("ID", "Pair", "Open Rate", "Current Rate", "Stop (%)", "Profit %", "Profit", "Dur.", "S/L", "Entry"),
        ]

        open_trades = ftuic.get_open_trades()

        current_time = datetime.now(tz=timezone.utc)
        #if ftuic.name in client_dfs and 'op_data' in client_dfs[ftuic.name]:
        #    trade_data = client_dfs[ftuic.name]['op_data']
        #    for idx, v in trade_data.iterrows():
        for t in open_trades:
            ttime = datetime.strptime(f"{t['open_date']}+00:00", self.app.TZFMT)
            open_orders = t['has_open_orders'] if 'has_open_orders' in t else (t['open_order_id'] is not None)
            pairstr = t['pair'] + ('*' if (open_orders and t['close_rate_requested'] is None) else '') + ('**' if (t['close_rate_requested'] is not None) else '')
            t_dir = "S" if t['is_short'] else "L"
            stop_profit = round(((t['stop_loss_abs'] - t['open_rate']) / t['stop_loss_abs'])*100, 2)

            row_data.append((
                # f"[@click=show_trade_info_dialog('{v['ID']}', '{ftuic.name}')]{v['ID']}[/]",
                # f"[@click=show_pair_candlestick_dialog('{v['Pair']}', '{ftuic.name}')]{v['Pair']}[/]",
                # f"{v['Open Rate']}",
                # f"{v['Current Rate']}",
                # fth.red_or_green(float(v['Stop %'])),
                # fth.red_or_green(float(v['Profit %']), justify='right'),
                # fth.red_or_green(float(v['Profit']), justify='right'),
                # str(v["Dur."]).split('.')[0].replace('0 days ', ''),
                # f"{v['S/L']}",
                # f"{v['Entry']}",
                # f"[@click=show_trade_info_dialog('{v['ID']}', '{ftuic.name}')]{v['ID']}[/]",

                f"{t['trade_id']}",
                f"[@click=update_chart('{ftuic.name}', '{pairstr}')]{pairstr}[/]",
                f"{t['open_rate']}",
                f"{t['current_rate']}",
                f"{t['stop_loss_abs']} [red]({stop_profit}%)" if stop_profit <= 0 else f"{t['stop_loss_abs']} [green]({stop_profit}%)",
                fth.red_or_green(float(t['profit_pct'])),
                fth.red_or_green(round(float(t['profit_abs']), 2)),
                f"{str(current_time-ttime).split('.')[0]}",
                f"{t_dir}",
                f"{t['enter_tag']}" if "enter_tag" in t else "",
            ))

        dt = self.query_one("#open-trades-table")
        table = fth.bot_open_trades_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False


    ## bot closed trades tab
    @work(group="bot_closed_trades_worker", exclusive=True, thread=True)
    def update_closed_trades_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]

        tab = self._get_tab(tab_id)
        self._render_closed_trades_summary(cl)

    def _render_closed_trades_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("ID", "Pair", "Profit %", "Profit", "Open Date", "Dur.", "Entry", "Exit"),
        ]

        if ftuic.name in client_dfs and 'cl_data' in client_dfs[ftuic.name]:
            trade_data = client_dfs[ftuic.name]['cl_data']
            for idx, v in trade_data.iterrows():
                row_data.append((
                    f"[@click=show_trade_info_dialog('{v['ID']}', '{ftuic.name}')]{v['ID']}[/]",
                    f"[@click=update_chart('{ftuic.name}', '{v['Pair']}')]{v['Pair']}[/]",
                    fth.red_or_green(float(v['Profit %']), justify='right'),
                    fth.red_or_green(float(v['Profit']), justify='right'),
                    f"[cyan]{str(v['Open Date']).split('+')[0]}",
                    str(v['Dur.']).split('.')[0].replace('0 days ', ''),
                    f"{v['Entry']}",
                    f"{v['Exit']}",
                ))

        dt = self.query_one("#closed-trades-table")
        table = fth.bot_closed_trades_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False


    ## bot tag summary tab
    @work(group="bot_tag_summary_worker", exclusive=True, thread=True)
    def update_tag_summary_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        cl = client_dict[bot_id]

        tab = self._get_tab(tab_id)
        self._render_tag_summary(cl)

    def _render_tag_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("Tag", "# Win", "# Loss", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit"),
        ]

        if ftuic.name in client_dfs and 'tag_data' in client_dfs[ftuic.name]:
            tag_data = client_dfs[ftuic.name]['tag_data']
            tag_data = tag_data.sort_values(by='Profit', ascending=False)

            for idx, v in tag_data.iterrows():
                row_data.append((
                    f"{v['Tag']}",
                    f"[green]{v['# Win']}/[red]{v['# Loss']}",
                    f"{v['Avg Dur.']}",
                    f"{v['Avg Win Dur.']}",
                    f"{v['Avg Loss Dur.']}",
                    fth.red_or_green(round(float(v['Profit']), 2), justify='right'),
                ))

        dt = self.query_one("#tag-summary-table")
        table = fth.bot_tag_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="bot_chart_worker", exclusive=True, thread=True)
    def update_chart(self, bot_id, pair=None):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        chart_container = self.query_one("#bot-chart")
        cw, ch = chart_container.container_size

        ## update chart
        cl = client_dict[bot_id]

        open_data = client_dfs[cl.name]['op_data'].copy() if cl.name in client_dfs and 'op_data' in client_dfs[cl.name] else pd.DataFrame()
        if not open_data.empty:
            if pair is None:
                if self.prev_chart_pair is None:
                    pair = open_data['Pair'].iloc[0]
                    self.prev_chart_pair = pair
                pair = self.prev_chart_pair
        else:
            if pair is None:
                if self.prev_chart_pair is not None:
                    pair = self.prev_chart_pair
                else:
                    close_data = client_dfs[cl.name]['cl_data'].copy() if cl.name in client_dfs and 'cl_data' in client_dfs[cl.name] else pd.DataFrame()

                    if not close_data.empty:
                        pair = close_data['Pair'].iloc[0]
                    else:
                        pair = f"BTC/{cl.get_client_config()['stake_currency']}"
                    self.prev_chart_pair = pair

        ckey = f"{pair}_{cl.get_client_config()['timeframe']}"
        if ckey not in self.chart_data:
            chart_container.loading = True
            data = cl.get_pair_dataframe(pair, limit=min(max(round(cw/2), 50), 200))
            if data is not None and not data.empty:
                self.chart_data[ckey] = data[["date","Open","Close","High","Low"]]
                self._render_chart(cl, pair, self.chart_data[ckey])
            else:
                self.notify(
                    f"No candle data for {pair} [{cl.get_client_config()['timeframe']} available. Is the pair in the whitelist?",
                    title=f"Error: [{pair}]",
                    severity="warning",
                )
        else:
            ## check if new data is available
            data = cl.get_pair_dataframe(pair, limit=1)
            if data is not None and not data.empty:
                last_date = self.chart_data[ckey].iloc[-1]['date']
                new_data = data[["date","Open","Close","High","Low"]].loc[data['date'] > last_date]
                if not new_data.empty:
                    chart_container.loading = True
                    self.chart_data[ckey] = pd.concat([self.chart_data[ckey], new_data])
                    self.chart_data[ckey].drop(self.chart_data[ckey].head(1).index,inplace=True)

                self._render_chart(cl, pair, self.chart_data[ckey])

            else:
                self.notify(
                    f"No candle data for {pair} [{cl.get_client_config()['timeframe']}] available. Is the pair in the whitelist?",
                    title=f"Error: [{pair}]",
                    severity="warning",
                )


    def _render_chart(self, ftuic, pair, data, trades=None):
        bot_id = ftuic.name
        chart_container = self.query_one("#bot-chart")
        cw, ch = chart_container.container_size

        data = data.copy()
        if not data.empty:
            cplt = chart_container.plt
            cplt.clear_data()
            cplt.clf()

            dfmt = "Y-m-d H:M:S"
            cplt.date_form(dfmt)
            data.rename(columns = {'date':'Date'}, inplace = True)
            data.set_index(pd.DatetimeIndex(data['Date']), inplace=True)
            data.index = data.index.tz_localize(None)

            dates = cplt.datetimes_to_string(data.index)

            cplt.title(f"{pair} ({ftuic.get_client_config()['timeframe']})")
            cplt.xlabel("Date")

            ymin = data['Low'].min()
            ymax = data['High'].max()
            yrange = ymax - ymin

            ## stop plotext crashing if having to plot tiny values
            ytick_labels = None
            if ymax < 0.00001 or ymin < 0.00001:
                print("Scaling up by 10000")
                data['Low'] = data['Low'] * 100000
                data['High'] = data['High'] * 100000
                data['Open'] = data['Open'] * 100000
                data['Close'] = data['Close'] * 100000
                ymin = data['Low'].min()
                ymax = data['High'].max()
                yrange = ymax - ymin
                yticks = [i for i in np.linspace(ymin,ymax,5)]
                ytick_labels = [f"{i/100000:.6f}" for i in np.linspace(ymin,ymax,5)]

            y_per_box = yrange / ch
            cplt.ylim(ymin-y_per_box, ymax+y_per_box)
            if ytick_labels is not None:
                cplt.yticks(yticks, ytick_labels)

            cplt.candlestick(dates, data)

            # if trades is not None and not trades.empty:
            #     o_events = []
            #     c_events = []
            #     for t in trades:
            #         o_events.append(t['open_rate'])
            #         if "close_rate" in t and t['close_rate'] is not None:
            #             c_events.append(t['close_rate'])

            #     cplt.scatter(dates, o_events, marker='o', color='cyan')
            #     cplt.scatter(dates, c_events, marker='x', color='yellow')

            self.app.call_from_thread(chart_container.refresh)
        chart_container.loading = False

    ## bot performance tab
    @work(group="perf_summary_worker", exclusive=True, thread=True)
    def update_performance_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        cl = client_dict[bot_id]

        tab = self._get_tab(tab_id)
        self._render_performance_summary(cl)

    def _render_performance_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("Pair", "# Trades", "Avg Profit %", "Total Profit"),
        ]

        if ftuic.name in client_dfs and 'perf_data' in client_dfs[ftuic.name]:
            perf_data = client_dfs[ftuic.name]['perf_data']
            perf_data = perf_data.sort_values(by='Total Profit', ascending=False)

            for idx, v in perf_data.iterrows():
                row_data.append((
                    f"{v['Pair']}",
                    f"{v['# Trades']}",
                    fth.red_or_green(float(v['Avg Profit %']), justify='right'),
                    fth.red_or_green(float(v['Total Profit']), justify='right'),
                ))

        dt = self.query_one("#perf-summary-table")
        table = fth.bot_perf_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    ## bot config tab
    # @work(group="config_worker", exclusive=True, thread=True)
    def update_config_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        if bot_id is not None and bot_id != 'Select.BLANK':
            cl = client_dict[bot_id]

            dt = self.query_one("#config-summary")
            c = fth.bot_config(cl.get_client_config())
            dt.update(c)

    @work(group="bot_logs_worker", exclusive=False, thread=True)
    def update_logs_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        if bot_id is not None and bot_id != 'Select.BLANK':
            cl = client_dict[bot_id]

            tab = self._get_tab(tab_id)
            logs = cl.get_logs(limit=self.app.loglimit)
            self._replace_logs(logs, tab)

    def _replace_logs(self, logs, tab):
        log = tab.query_one("#log")
        log.clear()
        log.write(logs)

    def update_whitelist(self, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        if bot_id is not None and bot_id != 'Select.BLANK':
            whitelist = cl.get_whitelist()

            wl = self.query_one("#whitelist")
            wl.clear()
            for pair in whitelist:
                wl.append(LabelItem(pair))

        wl.loading = False

    @on(ListView.Selected)
    def whitelist_pair_selected(self, event: ListView.Selected) -> None:
        event.stop()

        pair = str(event.item.label)
        self.prev_chart_pair = pair

        bot_id = self._get_bot_id_from_client_list()
        if bot_id is not None and bot_id != 'Select.BLANK':
            self.update_chart(bot_id, pair=pair)

    @on(Collapsible.Toggled)
    def toggle_collapsible(self, event: Collapsible.Toggled) -> None:
        event.stop()
        collap = event.collapsible

        collap_children = collap.query().filter(".bg-static-default")

        if collap.collapsed is False:
            for child in collap_children:
                child.loading = True

        bot_id = self._get_bot_id_from_client_list()
        if bot_id is not None and bot_id != 'Select.BLANK':
            if collap.id in self.COLLAP_FUNC_MAP:
                getattr(self, self.COLLAP_FUNC_MAP[collap.id])(bot_id)
        else:
            for child in collap_children:
                child.loading = False


    def debug(self, msg):
        debuglog = self.query_one("#debug-log")
        debuglog.write(msg)

## custom widget to easily get label values from ListItems
class LabelItem(ListItem):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose( self ) -> ComposeResult:
        yield Label(self.label)


class SettingsScreen(Screen):
    mkstr = "Settings:\n\n"

    def set_args(self, yaml_args):
        self.mkstr += str(yaml_args)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="above"):
            yield Static("FTUI Settings")

        with Container(id="parent-container"):
            with Container(id="right"):
                yield Markdown("-- Settings")
                yield Markdown(self.mkstr)

        yield Footer()


class HelpScreen(Screen):

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="above"):
            yield Static("FTUI Help")

        with Container(id="parent-container"):
            with Container(id="right"):
                yield Markdown("-- Hello")

        yield Footer()


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
        main, two, three = self.build_trade_info(trade_info)
        yield Container(
            main,
            two,
            three,
            id="info-dialog",
        )
        yield Footer()

    def build_trade_info(self, trade_info):

        close_rate= "-"
        close_date = "-"
        close_profit = "-"

        if trade_info['close_profit_abs'] is not None:
            # closed
            close_rate = trade_info['close_rate']
            close_date = trade_info['close_date']
            close_profit = f"{trade_info['close_profit_abs']} ({trade_info['close_profit_pct']}%)"

        main_text = (
            f"[b]Trade Id     : " + f"{self.trade_id}\n"
            f"[b]Pair         : " + f"{trade_info['pair']}\n"
            f"[b]Open Date    : " + f"{trade_info['open_date']}\n"
            f"[b]Entry Tag    : " + f"{trade_info['enter_tag']}\n"
            f"[b]Stake        : " + f"{trade_info['stake_amount']} {trade_info['quote_currency']}\n"
            f"[b]Amount       : " + f"{trade_info['amount']}\n"
            f"[b]Open Rate    : " + f"{trade_info['open_rate']}\n"
            f"[b]Close Rate   : " + f"{close_rate}\n"
            f"[b]Close Date   : " + f"{close_date}\n"
            f"[b]Close Profit : " + f"{close_profit}\n"
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
