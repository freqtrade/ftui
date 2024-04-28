from textual.app import ComposeResult
from textual.widgets import Label, ListItem


# custom widget to easily get label values from ListItems
class LabelItem(ListItem):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        yield Label(self.label)
