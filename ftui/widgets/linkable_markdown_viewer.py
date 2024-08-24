import webbrowser
from pathlib import Path

from textual import on
from textual.widgets import Markdown


class LinkableMarkdown(Markdown):

    @on(Markdown.LinkClicked)
    def handle_link(self, event: Markdown.LinkClicked) -> None:
        if not Path(event.href).exists():
            event.prevent_default()
            webbrowser.open(event.href)
