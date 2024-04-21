from pathlib import Path
import webbrowser

from textual import on
from textual.widgets import Markdown, MarkdownViewer

class LinkableMarkdownViewer(MarkdownViewer):

    @on(Markdown.LinkClicked)
    def handle_link(self, event: Markdown.LinkClicked) -> None:
        if not Path(event.href).exists():
            event.prevent_default()
            webbrowser.open(event.href)
