from datetime import datetime, timezone

import numpy as np
import pandas as pd
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import ScreenResume
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Label,
    ListView,
    Log,
    ProgressBar,
    Select,
    Sparkline,
    Static,
    TabbedContent,
    TabPane,
)
from textual.worker import get_current_worker
from textual_plotext import PlotextPlot

import ftui.ftui_helpers as fth
from ftui.screens.modal_screens import TradeInfoScreen
from ftui.widgets.label_item import LabelItem
from ftui.widgets.linkable_markdown_viewer import LinkableMarkdown
from ftui.widgets.timed_screen import TimedScreen


class MainBotScreen(TimedScreen):
    TAB_FUNC_MAP = {
        # tabs
        "open-trades-tab": "update_open_trades_tab",
        "closed-trades-tab": "update_closed_trades_tab",
        "tag-summary-tab": "update_tag_summary_tab",
        "perf-summary-tab": "update_performance_tab",
        "general-tab": "update_general_tab",
        "logs-tab": "update_logs_tab",
        "sysinfo-tab": "update_sysinfo_tab",
    }

    COLLAP_FUNC_MAP = {
        # collapsibles
        "bot-chrt-collap": "update_chart_container",
    }

    client_select_options = [("Select Bot Client...", "Select.BLANK")]
    prev_chart_pair = None
    chart_data = {}

    # LAYOUT
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="above-bot"):
            yield Select(options=self.client_select_options, allow_blank=False, id="client-select")

        with Container(id="parent-container"):
            with Container(id="right"):
                with Container(id="trades-summary"):
                    yield Static("Select a bot from the client list...", id="sel-bot-title")
                    yield Static(id="trades-summary-table", classes="bg-static-default")

                with Container(id="bot-chart-container"):
                    with Collapsible(
                        title="Candlestick Chart", id="bot-chrt-collap", collapsed=False
                    ):
                        with Horizontal(id="bot-chart-header"):
                            yield Button(
                                "Refresh", id="bot-refresh-chart-button", variant="success"
                            )

                        yield ListView(id="whitelist", classes="bg-static-default")
                        yield PlotextPlot(id="bot-chart", classes="bg-static-default")

                with TabbedContent(initial="open-trades-tab"):
                    with TabPane("Open Trades", id="open-trades-tab"):
                        yield Static(id="open-trades-table", classes="bg-static-default")

                    with TabPane("Closed Trades", id="closed-trades-tab"):
                        yield Static(id="closed-trades-table", classes="bg-static-default")

                    with TabPane("Tag Summary", id="tag-summary-tab"):
                        yield Static(id="tag-summary-table", classes="bg-static-default")

                    with TabPane("Performance", id="perf-summary-tab"):
                        yield Static(id="perf-summary-table", classes="bg-static-default")

                    with TabPane("General", id="general-tab"):
                        with Horizontal(id="bot-config-container"):
                            with Vertical(id="bot-general-vert"):
                                yield LinkableMarkdown(id="bot-general-markdown")

                                yield Static(id="bot-general-table")

                            yield LinkableMarkdown(id="bot-config-markdown")

                    with TabPane("Logs", id="logs-tab"):
                        yield Log(id="log")

                    with TabPane("Sysinfo", id="sysinfo-tab"):
                        with Container(id="bot-sysinfo-container"):
                            with Horizontal():
                                yield Label("CPU: ")
                                yield Sparkline(id="sysinfo-summary-cpu")
                                yield Label(id="sysinfo-cpu-text")
                            with Horizontal():
                                yield Label("RAM: ")
                                yield ProgressBar(
                                    id="sysinfo-progress-ram", total=100, show_eta=False
                                )

                    if self.app.debug_mode:
                        with TabPane("Debug", id="debug-tab"):
                            yield Log(id="debug-log")

        yield Footer()

    # MOUNT AND TIMERS
    def on_mount(self) -> None:
        self.update_select_options()

        update_one_sec_render = self.set_interval(1, self.update_per_sec)
        self.register_timer(f"{self.__class__.__name__}_1sec", update_one_sec_render)

        update_five_sec_render = self.set_interval(5, self.update_per_five_sec)
        self.register_timer(f"{self.__class__.__name__}_5sec", update_five_sec_render)

        update_one_min_render = self.set_interval(60, self.update_per_one_min)
        self.register_timer(f"{self.__class__.__name__}_1min", update_one_min_render)

    async def update_per_sec(self):
        if not self.screen.is_active:
            return

        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != "Select.BLANK":
            self.update_trades_summary(bot_id)

            tab_id = self._get_active_tab_id()
            if tab_id == "open-trades-tab":
                self.update_open_trades_tab(tab_id, bot_id)

    async def update_per_five_sec(self):
        if not self.screen.is_active:
            return

        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != "Select.BLANK":
            tab_id = self._get_active_tab_id()
            if tab_id != "open-trades-tab" and tab_id in self.TAB_FUNC_MAP:
                getattr(self, self.TAB_FUNC_MAP[tab_id])(tab_id, bot_id)

    async def update_per_one_min(self):
        if not self.screen.is_active:
            return

        bot_id = self._get_bot_id_from_client_list()
        if bot_id is not None and bot_id != "Select.BLANK":
            self.update_chart(bot_id, pair=self.prev_chart_pair)
            self.update_whitelist(bot_id)

    def action_update_chart(self, bot_id, pair) -> None:
        self.update_chart(bot_id, pair)

    def action_show_trade_info_dialog(self, trade_id, cl_name) -> None:
        tis = TradeInfoScreen()
        tis.trade_id = trade_id
        tis.client = self.app.client_dict[cl_name]
        self.app.push_screen(tis)

    # TAB EVENT STUFF
    def _get_bot_id_from_client_list(self):
        try:
            sel = self.query_one("#client-select")
            bot_id = str(sel.value)
            return bot_id
        except Exception:
            return None

    @on(Button.Pressed, "#bot-refresh-chart-button")
    def refresh_chart_button_pressed(self) -> None:
        bot_id = self._get_bot_id_from_client_list()

        chart_container = self.query_one("#bot-chart")
        #worker = get_current_worker()
        #if not worker.is_cancelled:
        #    self.app.call_from_thread(chart_container.loading, True)
        chart_container.loading = True
        self.update_chart(bot_id, pair=self.prev_chart_pair, refresh=True)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.tab.id
        bot_id = self._get_bot_id_from_client_list()

        if bot_id is not None and bot_id != "Select.BLANK":
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
        except Exception:
            return "open-trades-tab"

    def _get_tab(self, tab_id):
        return next(self.query(f"#{tab_id}").results(TabPane))

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        event.stop()

        bot_id = str(event.value)

        if bot_id != "Select.BLANK":
            self.query_one("#sel-bot-title").update(bot_id)
            self.update_trades_summary(bot_id)

            # update all tabs when select changed
            for tab in self.TAB_FUNC_MAP.keys():
                self.update_tab(tab, bot_id)

            self.update_whitelist(bot_id)
            self.update_chart(bot_id)

    @work(group="selswitch_workers", exclusive=True, thread=True)
    @on(ScreenResume)
    def update_select_options(self):
        client_dict = self.app.client_dict

        options = []

        for name, cl in client_dict.items():
            ot, mt = cl.get_open_trade_count()
            options.append((f"{name} : {ot}/{mt} active trades", name))

        self.client_select_options = options

        sel = self.query_one("#client-select")
        current_selection = sel.value

        sel.set_options(self.client_select_options)

        if current_selection is not None and current_selection != "Select.BLANK":
            sel.value = current_selection

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

    # bot trade summary
    @work(group="bot_summary_worker", exclusive=True, thread=True)
    def update_trades_summary(self, bot_id):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        cl = client_dict[bot_id]
        open_data = fth.get_open_dataframe_data(cl, client_dfs)
        closed_data = fth.get_closed_dataframe_data(cl, client_dfs)

        self._render_trades_summary(cl, open_data, closed_data)

    def _render_trades_summary(self, cl, open_data, closed_data):
        row_data = [
            # ("Bot Start", "# Trades", "Open Profit", "W/L", "Winrate", "Exp.",
            #  "Exp. Rate", "Med. W", "Med. L", "Total"),
        ]

        open_profit = 0
        mean_prof_w = 0
        mean_prof_l = 0
        median_win = 0
        median_loss = 0

        tpw = []
        tpl = []

        open_profit = 0

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
        bot_start_date = datetime.strptime(f"{t['bot_start_date']}+00:00", self.app.TZFMT).date()

        trade_cnt_str = (
            f"[cyan]{int(t['trade_count'])-int(t['closed_trade_count'])}"
            f"[white]/[purple]{t['closed_trade_count']}"
        )

        row_data.append(
            (
                f"{bot_start_date}",
                trade_cnt_str,
                fth.red_or_green(round(open_profit, 2), justify="right"),
                f"[green]{t['winning_trades']}/[red]{t['losing_trades']}",
                f"[cyan]{round(winrate, 1)}",
                f"[purple]{round(expectancy, 2)}",
                fth.red_or_green(round(expectancy_ratio, 2), justify="right"),
                f"[green]{median_win}",
                f"[red]{median_loss}",
                fth.red_or_green(pcc, justify="right"),
            )
        )

        dt = self.query_one("#trades-summary-table")
        table = fth.bot_trades_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)

        dt.loading = False

    # bot open trades tab
    @work(group="bot_open_trades_worker", exclusive=True, thread=True)
    def update_open_trades_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        self._render_open_trade_summary(cl)

    def _render_open_trade_summary(self, ftuic):
        row_data = [
            # ("ID", "Pair", "Open Rate", "Current Rate", "Stop (%)", "Profit %", "Profit", "Dur.", "S/L", "Entry"),
        ]

        current_time = datetime.now(tz=timezone.utc)

        open_trades = ftuic.get_open_trades()
        for t in open_trades:
            ttime = datetime.strptime(f"{t['open_date']}+00:00", self.app.TZFMT)
            open_orders = (
                t["has_open_orders"] if "has_open_orders" in t else (t["open_order_id"] is not None)
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

            stop_profit = "--- "
            if t["stop_loss_abs"] is not None and t["stop_loss_abs"] != 0:
                stop_profit = t['stop_loss_pct']
            stp_txt = (
                f"{t['stop_loss_abs']} [red]({stop_profit}%)"
                if stop_profit <= 0
                else f"{t['stop_loss_abs']} [green]({stop_profit}%)"
            )

            render_data = (
                f"[@click=screen.show_trade_info_dialog('{t['trade_id']}', '{ftuic.name}')]{t['trade_id']}[/]",
                f"[@click=screen.update_chart('{ftuic.name}', '{pairstr}')]{pairstr}[/]",
                f"{round(t['stake_amount'], 3)}",
            )

            if ftuic.get_client_config().get("trading_mode") != "spot":
                render_data = render_data + (f"{t['leverage']}",)

            render_data = render_data + (
                f"{num_orders}",
                f"{t['open_rate']}",
                f"{t['current_rate']}",
                stp_txt,
                fth.red_or_green(float(t["profit_pct"]), justify="right"),
                fth.red_or_green(rpfta, justify="right"),
                f"{str(current_time-ttime).split('.')[0]}",
                f"{t_dir}",
                f"{t['enter_tag']}" if "enter_tag" in t else "",
            )

            row_data.append(render_data)

        dt = self.query_one("#open-trades-table")
        table = fth.bot_open_trades_table(
            row_data, trading_mode=ftuic.get_client_config().get("trading_mode")
        )

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    # bot closed trades tab
    @work(group="bot_closed_trades_worker", exclusive=True, thread=True)
    def update_closed_trades_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        self._render_closed_trades_summary(cl)

    def _render_closed_trades_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("ID", "Pair", "Profit %", "Profit", "Open Date", "Dur.", "Entry", "Exit"),
        ]

        if ftuic.name in client_dfs and "cl_data" in client_dfs[ftuic.name]:
            trade_data = client_dfs[ftuic.name]["cl_data"]
            for idx, v in trade_data.iterrows():
                render_data = (
                    # Text.styled(str(v['ID']), Style(
                    #     meta={"@click": f"show_trade_info_dialog('{str(v['ID'])}', '{ftuic.name}')"},
                    #     color=self.app.COLOURS['link_col']
                    # )),
                    f"[@click=screen.show_trade_info_dialog('{v['ID']}', '{ftuic.name}')]{v['ID']}[/]",
                    f"[@click=screen.update_chart('{ftuic.name}', '{v['Pair']}')]{v['Pair']}[/]",
                    f"{v['Stake Amount']}",
                )

                if ftuic.get_client_config().get("trading_mode") != "spot":
                    render_data = render_data + (f"{v['Leverage']}",)

                render_data = render_data + (
                    fth.red_or_green(float(v["Profit %"]), justify="right"),
                    fth.red_or_green(float(v["Profit"]), justify="right"),
                    f"[cyan]{str(v['Open Date']).split('+')[0]}",
                    str(v["Dur."]).split(".")[0].replace("0 days ", ""),
                    f"{v['Entry']}",
                    f"{v['Exit']}",
                )

                row_data.append(render_data)

        dt = self.query_one("#closed-trades-table")
        table = fth.bot_closed_trades_table(
            row_data, trading_mode=ftuic.get_client_config().get("trading_mode")
        )

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    # bot tag summary tab
    @work(group="bot_tag_summary_worker", exclusive=True, thread=True)
    def update_tag_summary_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        self._render_tag_summary(cl)

    def _render_tag_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("Tag", "# Win", "# Loss", "Avg Dur.", "Avg Win Dur.", "Avg Loss Dur.", "Profit"),
        ]

        tag_data = fth.get_tag_dataframe_data(ftuic, client_dfs)
        tag_data = tag_data.sort_values(by="Profit", ascending=False)

        for idx, v in tag_data.iterrows():
            row_data.append(
                (
                    f"{v['Tag']}",
                    f"[green]{v['# Win']}/[red]{v['# Loss']}",
                    f"{v['Avg Dur.']}",
                    f"{v['Avg Win Dur.']}",
                    f"{v['Avg Loss Dur.']}",
                    fth.red_or_green(round(float(v["Profit"]), 2), justify="right"),
                )
            )

        dt = self.query_one("#tag-summary-table")
        table = fth.bot_tag_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="bot_chart_worker", exclusive=False, thread=True)
    def update_chart(self, bot_id, pair=None, refresh=False):
        client_dict = self.app.client_dict
        client_dfs = self.app.client_dfs

        chart_container = self.query_one("#bot-chart")
        cw, ch = chart_container.container_size

        cl = client_dict[bot_id]
        open_data = fth.get_open_dataframe_data(cl, client_dfs)
        if not open_data.empty:
            if pair is None:
                if self.prev_chart_pair is None:
                    pair = open_data["Pair"].iloc[0]
                    self.prev_chart_pair = pair
                pair = self.prev_chart_pair
            else:
                self.prev_chart_pair = pair
        else:
            if pair is None:
                if self.prev_chart_pair is not None:
                    pair = self.prev_chart_pair
                else:
                    closed_data = fth.get_closed_dataframe_data(cl, client_dfs)

                    if not closed_data.empty:
                        pair = closed_data["Pair"].iloc[0]
                    else:
                        pair = f"BTC/{cl.get_client_config()['stake_currency']}"
                    self.prev_chart_pair = pair
            else:
                self.prev_chart_pair = pair

        ckey = f"{pair}_{cl.get_client_config()['timeframe']}"
        if ckey not in self.chart_data or refresh:
            worker = get_current_worker()
            if not worker.is_cancelled:
                self.app.call_from_thread(chart_container.set_loading, True)

            data = cl.get_pair_dataframe(pair, limit=min(max(round(cw / 2), 50), 200))
            if data is not None and not data.empty:
                self.chart_data[ckey] = data[["date", "Open", "Close", "High", "Low"]]
                self._render_chart(cl, pair, self.chart_data[ckey])
            else:
                msg = (
                    f"No data for {pair} [{cl.get_client_config()['timeframe']}] available. "
                    f"Is the pair in the whitelist?"
                )
                self.notify(
                    msg,
                    title=f"Error: [{pair}]",
                    severity="warning",
                )
        else:
            # check if new data is available
            data = cl.get_pair_dataframe(pair, limit=1)
            if data is not None and not data.empty:
                last_date = self.chart_data[ckey].iloc[-1]["date"]
                new_data = data[["date", "Open", "Close", "High", "Low"]].loc[
                    data["date"] > last_date
                ]
                if not new_data.empty:
                    worker = get_current_worker()
                    if not worker.is_cancelled:
                        self.app.call_from_thread(chart_container.set_loading, True)

                    self.chart_data[ckey] = pd.concat([self.chart_data[ckey], new_data])
                    self.chart_data[ckey].drop(self.chart_data[ckey].head(1).index, inplace=True)

                self._render_chart(cl, pair, self.chart_data[ckey])

            else:
                msg = (
                    f"No data for {pair} [{cl.get_client_config()['timeframe']}] available. "
                    f"Is the pair in the whitelist?"
                )
                self.notify(
                    msg,
                    title=f"Error: [{pair}]",
                    severity="warning",
                )

    def _render_chart(self, ftuic, pair, data):
        chart_container = self.query_one("#bot-chart")
        cw, ch = chart_container.container_size

        data = data.copy()
        if not data.empty:
            cplt = chart_container.plt
            cplt.clear_data()
            cplt.clf()

            dfmt = "Y-m-d H:M:S"
            cplt.date_form(dfmt)
            data.rename(columns={"date": "Date"}, inplace=True)
            data.set_index(pd.DatetimeIndex(data["Date"]), inplace=True)
            data.drop(columns=["Date"], inplace=True)
            data.index = data.index.tz_localize(None)

            if len(data.index) > 0:
                min_date = data.index.min()
                max_date = data.index.max()

                ymin = data["Low"].min()
                ymax = data["High"].max()
                yrange = ymax - ymin
                y_per_box = yrange / ch

                # candlestick
                dates = cplt.datetimes_to_string(data.index)

                cplt.title(f"{pair} ({ftuic.get_client_config()['timeframe']})")
                cplt.xlabel("Date")

                # stop plotext crashing if having to plot tiny values
                ytick_labels = None
                if ymax < 0.00001 or ymin < 0.00001:
                    print("Scaling up by 10000")
                    data["Low"] = data["Low"] * 100000
                    data["High"] = data["High"] * 100000
                    data["Open"] = data["Open"] * 100000
                    data["Close"] = data["Close"] * 100000
                    ymin = data["Low"].min()
                    ymax = data["High"].max()
                    yrange = ymax - ymin
                    yticks = [i for i in np.linspace(ymin, ymax, 5)]
                    ytick_labels = [f"{i/100000:.6f}" for i in np.linspace(ymin, ymax, 5)]

                cplt.ylim(ymin - y_per_box, ymax + y_per_box)
                if ytick_labels is not None:
                    cplt.yticks(yticks, ytick_labels)

                cplt.candlestick(dates, data)

                # scatter
                client_dfs = self.app.client_dfs
                open_data = fth.get_open_dataframe_data(ftuic, client_dfs)
                open_data = open_data[open_data["Pair"] == pair]
                closed_data = fth.get_closed_dataframe_data(ftuic, client_dfs)
                closed_data = closed_data[closed_data["Pair"] == pair]

                all_trades = pd.concat([open_data, closed_data])

                if all_trades is not None and not all_trades.empty:
                    all_trades["Open Date"] = pd.to_datetime(
                        all_trades["Open Date"]
                    ).dt.tz_localize(None)
                    all_trades["Close Date"] = pd.to_datetime(
                        all_trades["Close Date"]
                    ).dt.tz_localize(None)

                    o_events = []
                    o_dates = []
                    c_events = []
                    c_dates = []
                    for idx, t in all_trades.iterrows():
                        odate = t["Open Date"]

                        trade_dir = t["S/L"]
                        open_text = f"Long {t['Profit %']}%"
                        open_marker = "\u25b2"

                        if trade_dir == "S":
                            open_text = f"Short {t['Profit %']}%"
                            open_marker = "\u25bc"

                        if odate < max_date:
                            if odate > min_date:
                                o_events.append(t["Open Rate"])
                                o_dates.append(odate.strftime(self.app.DFMT))
                                cplt.text(
                                    open_text,
                                    x=odate.strftime(self.app.DFMT),
                                    y=t["Open Rate"] + (y_per_box * 2),
                                    alignment="left",
                                    color=self.app.COLOURS["candlestick_trade_text_col"],
                                )

                        if "Close Rate" in t:
                            if t["Close Rate"] is not None and not pd.isna(t["Close Rate"]):
                                if t["Close Date"] > min_date:
                                    c_events.append(t["Close Rate"])
                                    c_dates.append(t["Close Date"].strftime(self.app.DFMT))

                    if len(o_dates) > 0 or len(c_dates) > 0:
                        cplt.scatter(
                            o_dates,
                            o_events,
                            marker=open_marker,
                            color=self.app.COLOURS["candlestick_trade_open_col"],
                        )
                        cplt.scatter(
                            c_dates,
                            c_events,
                            marker="x",
                            color=self.app.COLOURS["candlestick_trade_close_col"],
                        )

                xticks = [
                    d.strftime(self.app.DFMT)
                    for d in pd.date_range(start=min_date, end=max_date, periods=5)
                ]

                cplt.xticks(xticks)

                self.app.call_from_thread(chart_container.refresh)
            else:
                self.notify(
                    "Please try clicking Refresh above to retry",
                    title=f"Error: No data available for {pair}",
                    severity="warning",
                )

        self.app.call_from_thread(chart_container.set_loading, False)

    # bot performance tab
    @work(group="perf_summary_worker", exclusive=True, thread=True)
    def update_performance_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        self._render_performance_summary(cl)

    def _render_performance_summary(self, ftuic):
        client_dfs = self.app.client_dfs

        row_data = [
            # ("Pair", "# Trades", "Avg Profit %", "Total Profit"),
        ]

        perf_data = fth.get_perf_dataframe_data(ftuic, client_dfs)
        perf_data = perf_data.sort_values(by="Total Profit", ascending=False)

        for idx, v in perf_data.iterrows():
            row_data.append(
                (
                    f"{v['Pair']}",
                    f"{v['# Trades']}",
                    fth.red_or_green(float(v["Avg Profit %"]), justify="right"),
                    fth.red_or_green(float(v["Total Profit"]), justify="right"),
                )
            )

        dt = self.query_one("#perf-summary-table")
        table = fth.bot_perf_summary_table(row_data)

        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(dt.update, table)
        dt.loading = False

    @work(group="bot_general_worker", exclusive=True, thread=True)
    def update_general_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        if bot_id is not None and bot_id != "Select.BLANK":
            cl = client_dict[bot_id]

            gdm = self.query_one("#bot-general-markdown")
            gc = fth.bot_general_info(cl)
            self.app.call_from_thread(gdm.update, gc)

            gdt = self.query_one("#bot-general-table")
            gm = fth.bot_general_metrics_table(cl)
            self.app.call_from_thread(gdt.update, gm)

            cdt = self.query_one("#bot-config-markdown")
            cc = fth.bot_config(cl)
            self.app.call_from_thread(cdt.update, cc)

    @work(group="bot_logs_worker", exclusive=False, thread=True)
    def update_logs_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        if bot_id is not None and bot_id != "Select.BLANK":
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
        if bot_id is not None and bot_id != "Select.BLANK":
            whitelist = cl.get_whitelist()

            wl = self.query_one("#whitelist")
            wl.clear()

            if self.prev_chart_pair is not None and self.prev_chart_pair in whitelist:
                wl.append(LabelItem(self.prev_chart_pair))
                whitelist.remove(self.prev_chart_pair)

            for pair in whitelist:
                wl.append(LabelItem(pair))

        wl.loading = False

    @on(ListView.Selected)
    def whitelist_pair_selected(self, event: ListView.Selected) -> None:
        event.stop()

        pair = str(event.item.label)
        self.prev_chart_pair = pair

        bot_id = self._get_bot_id_from_client_list()
        if bot_id is not None and bot_id != "Select.BLANK":
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
        if bot_id is not None and bot_id != "Select.BLANK":
            if collap.id in self.COLLAP_FUNC_MAP:
                getattr(self, self.COLLAP_FUNC_MAP[collap.id])(bot_id)
        else:
            for child in collap_children:
                child.loading = False

    @work(group="sysinfo_summary_worker", exclusive=True, thread=True)
    def update_sysinfo_tab(self, tab_id, bot_id):
        client_dict = self.app.client_dict

        cl = client_dict[bot_id]
        self._render_sysinfo(cl)

    def _render_sysinfo(self, ftuic):
        sysinfo = ftuic.get_sys_info()

        dtc = self.query_one("#sysinfo-summary-cpu")
        dtt = self.query_one("#sysinfo-cpu-text")
        dtp = self.query_one("#sysinfo-progress-ram")

        if sysinfo is not None and "cpu_pct" in sysinfo:
            worker = get_current_worker()
            if not worker.is_cancelled:
                dtc.data = sysinfo["cpu_pct"]
                dtc.styles.width = len(sysinfo["cpu_pct"])
                dtt.update(f"{np.mean(sysinfo['cpu_pct']):>3.0f}%")
                dtp.update(progress=sysinfo["ram_pct"])

    def debug(self, msg):
        debuglog = self.query_one("#debug-log")
        debuglog.write(msg)
