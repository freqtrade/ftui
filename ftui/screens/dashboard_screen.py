from datetime import datetime

import pandas as pd
from rich.table import Table
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Collapsible,
    Digits,
    Footer,
    Header,
    Label,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection
from textual.worker import get_current_worker
from textual_plotext import PlotextPlot

import ftui.ftui_helpers as fth
from ftui.widgets.timed_screen import TimedScreen


class DashboardScreen(TimedScreen):
    COLLAP_FUNC_MAP = {
        # collapsibles
        "dsh-cp-collap": "update_cumulative_profit_plot",
    }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="above"):
            with Container(id="all-open-profit"):
                yield Label("Open")
                yield Digits(id="all-bot-summary-open-profit")

            with Container(id="all-closed-profit"):
                yield Label("Closed")
                yield Digits(id="all-bot-summary-closed-profit")

            with Container(id="all-daily-profit"):
                yield Label("Daily")
                yield Digits(id="all-bot-summary-daily-profit")
                yield Static(id="yesterday-profit")

            with Container(id="all-weekly-profit"):
                yield Label("Weekly")
                yield Digits(id="all-bot-summary-weekly-profit")
                yield Static(id="last-week-profit")

            with Container(id="all-monthly-profit"):
                yield Label("Monthly")
                yield Digits(id="all-bot-summary-monthly-profit")
                yield Static(id="last-month-profit")

        with Container(id="parent-container"):
            with Container(id="dash-container"):
                with Container(id="dash-all-trade-summary"):
                    yield Static(id="all-trade-summary-table")

                with Container(id="dash-collapsibles"):
                    with Collapsible(title="All Open Trades", id="dsh-op-collap", collapsed=False):
                        yield Static(id="all-open-trades-table", classes="bg-static-default collap-update")

                    with Collapsible(title="All Closed Trades", id="dsh-cl-collap", collapsed=True):
                        with Container(id="dash-closed-profit-container"):
                            yield Static(id="dash-closed-profit", classes="bg-static-default collap-update")

                    with Collapsible(title="Cumulative Profit", id="dsh-cp-collap", collapsed=True):
                        with Container(id="dsh-chart-container"):
                            with Horizontal(id="dsh-chart-header"):
                                yield Button(
                                    "Refresh", id="dash-refresh-chart-button", variant="success"
                                )
                            yield SelectionList(id="dsh-chart-bot-list", classes="bg-static-default")
                            yield PlotextPlot(id="dash-cumprof-profit", classes="bg-static-default collap-update")

                    # with Collapsible(title="Daily Trade Summary",
                    #                  id="dsh-dt-collap",
                    #                  collapsed=True):
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

        dsh_chart_bot_list = self.query_one("#dsh-chart-bot-list")
        for n, cl in self.app.client_dict.items():
            dsh_chart_bot_list.add_option(
                Selection(n, n, True)
            )

        update_one_sec_render = self.set_interval(1, self.update_per_sec)
        self.register_timer(f"{self.__class__.__name__}_1sec", update_one_sec_render)

        update_five_sec_render = self.set_interval(5, self.update_per_five_sec)
        self.register_timer(f"{self.__class__.__name__}_5sec", update_five_sec_render)

    async def update_per_sec(self):
        if not self.screen.is_active:
            return

        self.update_dashboard_all_bot_summary()

        dsh_op_collap = self.query_one("#dsh-op-collap")
        if dsh_op_collap.collapsed is False:
            self.update_dashboard_all_open_trades()

    async def update_per_five_sec(self):
        if not self.screen.is_active:
            return

        self.update_dashboard_all_trade_summary()

        dsh_cl_collap = self.query_one("#dsh-cl-collap")
        if dsh_cl_collap.collapsed is False:
            self.update_dashboard_all_closed_trades()

        dsh_cp_collap = self.query_one("#dsh-cp-collap")
        if dsh_cp_collap.collapsed is False:
            self.update_cumulative_profit_plot()

    def _render_open_trade_data(self, data, trading_mode="spot"):
        row_data = []

        for idx, v in data.iterrows():
            # bot_name = v['Bot']

            render_data = (
                # f"[@click=app.switch_to_bot('{bot_name}')]{bot_name}[/]",
                f"{v['Bot']}",
                f"{v['ID']}",
                f"{v['Pair']}",
                f"{round(v['Stake Amount'], 3)}",
            )

            if trading_mode != "spot":
                render_data = render_data + (f"{v['Leverage']}",)

            render_data = render_data + (
                f"{v['# Orders']}",
                f"{round(v['Open Rate'], 3)}",
                f"{v['Current Rate']}",
                fth.red_or_green(float(v["Stop %"])),
                fth.red_or_green(float(v["Max %"]), justify="left"),
                fth.red_or_green(float(v["Profit %"]), justify="right"),
                fth.red_or_green(float(v["Profit"]), justify="left"),
                str(v["Dur."]).split(".")[0].replace("0 days ", ""),
                f"{v['S/L']}",
                f"{v['Entry']}",
            )

            row_data.append(render_data)

        return row_data

    def _render_closed_trade_data(self, data):
        row_data = []
        data = data.sort_values(by="Close Date", ascending=False)

        for idx, v in data.iterrows():
            row_data.append(
                (
                    f"{v['Bot']}",
                    f"{v['ID']}",
                    f"{v['Pair']}",
                    fth.red_or_green(float(v["Profit %"]), justify="right"),
                    fth.red_or_green(float(v["Profit"]), justify="right"),
                    f"[cyan]{str(v['Open Date']).split('+')[0]}",
                    str(v["Dur."]).split(".")[0].replace("0 days ", ""),
                    f"{v['Entry']}",
                    f"{v['Exit']}",
                )
            )

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
            open_data = fth.get_open_dataframe_data(cl, client_dfs)
            closed_data = fth.get_closed_dataframe_data(cl, client_dfs)

            tot_profit = 0
            if not open_data.empty:
                tot_profit = round(open_data["Profit"].sum(), 2)

            pcc = 0
            if not closed_data.empty:
                pcc = round(closed_data["Profit"].sum(), 2)

            closed_profit = closed_profit + pcc
            open_profit = open_profit + tot_profit

            d = cl.get_daily_profit(days=2)
            if d is not None and "data" in d and d["data"]:
                daily_profit = daily_profit + d["data"][0]["abs_profit"]
                yesterday_profit = d["data"][1]["abs_profit"]
            w = cl.get_weekly_profit(weeks=2)
            if w is not None and "data" in w and w["data"]:
                weekly_profit = weekly_profit + w["data"][0]["abs_profit"]
                last_week_profit = w["data"][1]["abs_profit"]
            m = cl.get_monthly_profit(months=2)
            if m is not None and "data" in m and m["data"]:
                monthly_profit = monthly_profit + m["data"][0]["abs_profit"]
                last_month_profit = m["data"][1]["abs_profit"]

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
            self.app.call_from_thread(
                ypsd.update, Text(f"{round(yesterday_profit, 2)}", justify="center")
            )
            self.app.call_from_thread(
                lwpsd.update, Text(f"{round(last_week_profit, 2)}", justify="center")
            )
            self.app.call_from_thread(
                lmpsd.update, Text(f"{round(last_month_profit, 2)}", justify="center")
            )

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

        trading_mode = "spot"

        all_open_df = pd.DataFrame()
        for n, cl in client_dict.items():
            # if any bots are in futures mode, add leverage column
            tm = cl.get_client_config().get("trading_mode", "spot")
            if tm != "spot":
                trading_mode = tm
            if cl.name in client_dfs and "op_data" in client_dfs[cl.name]:
                data = client_dfs[cl.name]["op_data"].copy()
                if not data.empty:
                    all_open_df = pd.concat([all_open_df, data])

        row_data = self._render_open_trade_data(
            all_open_df, trading_mode=trading_mode
        )

        dt = self.query_one("#all-open-trades-table")
        table = fth.dash_open_trades_table(
            row_data, trading_mode=trading_mode
        )

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="dash_all_closed_worker", exclusive=True, thread=True)
    def update_dashboard_all_closed_trades(self, num_closed_trades=5) -> Table:
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        all_closed_df = pd.DataFrame()
        for n, cl in client_dict.items():
            if cl.name in client_dfs and "cl_data" in client_dfs[cl.name]:
                data = client_dfs[cl.name]["cl_data"].copy()
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
            open_data = fth.get_open_dataframe_data(cl, client_dfs)
            closed_data = fth.get_closed_dataframe_data(cl, client_dfs)

            open_profit = 0
            mean_prof_w = 0
            mean_prof_l = 0
            median_win = 0
            median_loss = 0

            tpw = []
            tpl = []

            if not open_data.empty:
                open_profit = round(open_data["Profit"].sum(), 2)

            if "Profit" in closed_data.columns:
                tpw = closed_data.loc[closed_data["Profit"] >= 0, "Profit"]
                tpl = closed_data.loc[closed_data["Profit"] < 0, "Profit"]

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

            expectancy_ratio = float("inf")
            if abs(mean_prof_l) > 0:
                expectancy_ratio = ((1 + (mean_prof_w / abs(mean_prof_l))) * (winrate / 100)) - 1

            expectancy = ((winrate / 100) * mean_prof_w) - ((loserate / 100) * mean_prof_l)

            t = cl.get_total_profit()
            if t is None:
                return []

            pcc = round(float(t["profit_closed_coin"]), 2)
            bot_start_date = datetime.strptime(
                f"{t['bot_start_date']}+00:00", self.app.TZFMT
            ).date()

            all_open_profit = all_open_profit + open_profit
            all_profit = all_profit + pcc
            all_wins = all_wins + t["winning_trades"]
            all_losses = all_losses + t["losing_trades"]

            trade_cnt_str = (
                f"[cyan]{int(t['trade_count'])-int(t['closed_trade_count'])}"
                f"[white]/[purple]{t['closed_trade_count']}"
            )

            row_data.append(
                (
                    f"{n}",
                    f"{bot_start_date}",
                    trade_cnt_str,
                    fth.red_or_green(round(open_profit, 2), justify="right"),
                    f"[green]{t['winning_trades']}/[red]{t['losing_trades']}",
                    f"[cyan]{round(winrate, 1)}",
                    f"[purple]{round(expectancy, 2)}",
                    fth.red_or_green(round(expectancy_ratio, 2)),
                    fth.red_or_green(
                        round(median_win, 2), justify="right"
                    ),  # f"[green]{median_win}",
                    fth.red_or_green(
                        round(median_loss, 2), justify="left"
                    ),  # f"[red]{median_loss}",
                    fth.red_or_green(pcc, justify="right"),
                )
            )

        footer = {
            "all_open_profit": fth.red_or_green(round(all_open_profit, 2), justify="right"),
            "num_wins_losses": f"[green]{all_wins}/[red]{all_losses}",
            "all_total_profit": fth.red_or_green(round(all_profit, 2), justify="right"),
        }

        dt = self.query_one("#all-trade-summary-table")
        table = fth.dash_trades_summary(row_data, footer)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)

        ats = self.query_one("#dash-all-trade-summary")
        ats.loading = False

    @work(group="dash_chart_worker", exclusive=False, thread=True)
    def update_cumulative_profit_plot(self, bot_list=None):
        client_dfs = self.app.client_dfs

        bot_list = self.query_one("#dsh-chart-bot-list").selected

        all_cum_data = pd.DataFrame()
        if "all_closed" in client_dfs:
            if bot_list is None or not bot_list:
                all_cum_data = fth.dash_cumulative_profit_plot_data(
                    client_dfs["all_closed"]
                )
            else:
                all_cum_data = fth.dash_cumulative_profit_plot_data(
                    client_dfs["all_closed"],
                    bot_list=bot_list
                )

        if "plot_cumprof" in all_cum_data.columns:
            chart_container = self.query_one("#dash-cumprof-profit")
            cplt = chart_container.plt
            cplt.clear_data()
            cplt.clf()

            dfmt = "Y-m-d"
            cplt.date_form(dfmt)

            all_cum_data.index = all_cum_data.index.tz_localize(None)

            dates = cplt.datetimes_to_string(all_cum_data.index)

            cplt.plot(
                dates,
                all_cum_data["plot_cumprof"].values,
                color=self.app.COLOURS.profit_chart_col,
            )

            cplt.ylim(
                all_cum_data["plot_cumprof"].min() * 0.99,
                all_cum_data["plot_cumprof"].max() * 1.01,
            )
            cplt.ylabel("Profit")

            self.app.call_from_thread(chart_container.refresh)

            worker = get_current_worker()
            if not worker.is_cancelled:
                self.app.call_from_thread(chart_container.set_loading, False)

    @on(SelectionList.SelectedChanged)
    def update_cum_plot_from_list(self) -> None:
        chart_container = self.query_one("#dash-cumprof-profit")
        chart_container.loading = True
        self.update_cumulative_profit_plot()

    @on(Button.Pressed, "#dash-refresh-chart-button")
    def refresh_dash_chart_button_pressed(self) -> None:
        self.update_cum_plot_from_list()

    @on(Collapsible.Toggled)
    def toggle_collapsible(self, event: Collapsible.Toggled) -> None:
        event.stop()
        collap = event.collapsible

        collap_children = collap.query().filter(".collap-update")

        if collap.collapsed is False:
            for child in collap_children:
                child.loading = True

        if collap.id in self.COLLAP_FUNC_MAP:
            getattr(self, self.COLLAP_FUNC_MAP[collap.id])()
        else:
            for child in collap_children:
                child.loading = False
