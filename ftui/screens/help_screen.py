from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Static,
)

from ftui.widgets.linkable_markdown_viewer import LinkableMarkdown


class HelpScreen(Screen):
    help_file_path = Path(__file__).parent.parent / "md" / "help.md"

    header_str = """
    ███████╗████████╗██╗   ██╗██╗
    ██╔════╝╚══██╔══╝██║   ██║██║
    █████╗     ██║   ██║   ██║██║
    ██╔══╝     ██║   ██║   ██║██║
    ██║        ██║   ╚██████╔╝██║
    ╚═╝        ╚═╝    ╚═════╝ ╚═╝
    """

    @property
    def markdown_viewer(self) -> LinkableMarkdown:
        """Get the Markdown widget."""
        return self.query_one(LinkableMarkdown)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Container(id="help-above"):
            yield Static(self.header_str)

        with Container(id="parent-container"):
            with Container(id="right"):
                yield LinkableMarkdown()

        yield Footer()

    async def on_mount(self) -> None:
        self.markdown_viewer.focus()
        try:
            await self.markdown_viewer.load(self.help_file_path)
        except FileNotFoundError:
            msg = f"Unable to load help file: {self.help_file_path!r}"
            self.notify(
                msg,
                title="Error:",
                severity="warning",
            )
