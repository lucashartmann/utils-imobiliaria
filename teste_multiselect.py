from textual.app import App, ComposeResult
from textual.widgets import ListView, ListItem, Button, Static
from textual.reactive import reactive
from textual import events
from textual_image.widget import Image

class MultiSelectListItem(ListItem):
    selected = reactive(False)

    
    def on_click(self, event: events.Click) -> None:
        self.selected = not self.selected
        self.refresh()

    class Selected(events.Event):
        def __init__(self, item):
            self.item = item

class MultiSelectListView(ListView):
    def get_selected_items(self):
        return [item for item in self.children if getattr(item, 'selected', False)]

class MyApp(App):
    CSS_PATH = "app.tcss"
    def compose(self) -> ComposeResult:
        self.list_view = MultiSelectListView(
            MultiSelectListItem(Image("Imagens\\img_3.jpg")),
            MultiSelectListItem(Image("Imagens\\img_4.jpg")),
            # MultiSelectListItem(Image("Imagens\\img_5.jpg")),
            MultiSelectListItem(Image("Imagens\\img_6.jpg")),
        )
        yield self.list_view
        yield Button("Mostrar Selecionados")

    def on_button_pressed(self, event: Button.Pressed):
        selecionados = self.list_view.get_selected_items()
        labels = [item for item in selecionados]
        self.notify(f"Selecionados: {', '.join(labels)}")

if __name__ == "__main__":
    MyApp().run()
