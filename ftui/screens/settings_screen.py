from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Static,
)


class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="settings-above"):
            yield Static("FTUI Settings")
            yield Button("Save", id="bot-save-settings-button", variant="success")

        with Container(id="parent-container"):
            with Container(id="right"):
                with Container(id="settings-left"):
                    yield Label("Server List")
                with Container(id="settings-right"):
                    yield Label("General Config")

        yield Footer()

    def on_mount(self):
       self.update_settings(self.app.settings)

    # @on(ScreenResume)
    # def on_resume(self):
    #     self.update_settings(self.app.settings)

    @on(Button.Pressed, "#bot-save-settings-button")
    def save_settings_button_pressed(self) -> None:
        self.notify(
            "Saving of settings is not currently implemented",
            title="Not Implemented",
            severity="warning",
        )

    def update_settings(self, s):
        settings_left = self.query_one("#settings-left")
        settings_right = self.query_one("#settings-right")

        for setting in s:
            if setting != "yaml":
                if isinstance(s[setting], bool):
                    # output checkbox
                    c = Checkbox(setting, s[setting])
                    settings_right.mount(c)
                elif isinstance(s[setting], str):
                    # output textbox
                    c = Horizontal(id=f"settings-txt-{setting}")
                    c.mount(Label(setting), Input(s[setting]))
                    settings_right.mount(c)
                elif isinstance(s[setting], dict):
                    # nested
                    print("bloop")
                elif isinstance(s[setting], list):
                    if setting == "servers":
                        # output server list
                        try:
                            settings_servers = self.query_one(f"#settings-{setting}")
                        except Exception:
                            settings_servers = Container(id=f"settings-{setting}")
                            settings_left.mount(settings_servers)

                        for server in s[setting]:
                            t = Checkbox(
                                f"{server['name']} [{server['ip']}:{server['port']}]",
                                server.get("enabled", True),
                            )
                            settings_servers.mount(t)
