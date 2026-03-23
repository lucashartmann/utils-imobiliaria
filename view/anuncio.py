from textual.app import App
from textual.containers import Center, Horizontal, Grid
from textual.screen import Screen
from utils.selecionar_arquivos import selecionar_arquivos
from textual.widgets import Button, Input, Static, Tab, Tabs, TextArea
from model.modelo import Modelo
from textual_image.widget import Image


class Anuncio(Screen):
    
    CSS_PATH = ["css/base.tcss", "css/anuncio.tcss"]

    def __init__(self, name=None, id=None, classes=None):
        super().__init__(name, id, classes)
        self.imagens = []
        self.modelo_atual = Modelo()
        self.modelo_atual.modelo = "llava:13b"

    def vericar_modelos_imagem(self):

        if not self.modelo_atual.listar_nome_modelos():
            self.notify("Não há nenhum modelo do ollama instalado")
            return

        for modelo in self.modelo_atual.listar_nome_modelos():
            self.modelo_atual.modelo = modelo
            if self.modelo_atual.suporta_imagem:
                return
            else:
                self.modelo_atual.modelo = None
                continue
            
    def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        if event.tabs.active == self.query_one("#tab_imagens", Tab).id:
                self.app.pop_screen()
     

    def on_mount(self):
        if not self.modelo_atual.modelo:
            self.vericar_modelos_imagem()
            if not self.modelo_atual.modelo:
                self.notify("Nenhum modelo suporta imagem")
                
    def on_screen_resume(self):
        self.query_one(Tabs).active = self.query_one(
            "#tab_anuncio", Tab).id

    def compose(self):
        yield Tabs(Tab('Imagens', id="tab_imagens"), Tab("Anúncio", id="tab_anuncio"))
        with Center():
            yield Button("Selecionar Imagem")
        # yield Image()
        with Center(id="center_grid"):
            yield Grid()
        with Center():
            yield Button("Gerar Anúncio")
        with Horizontal():
            yield Static("Título:")
            yield Input(id="titulo", placeholder="Titulo do anúncio")
        with Horizontal():
            yield Static("Descrição:")
            yield Input(id="descricao", placeholder="Descrição do anúncio")
            
        yield TextArea()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.label:
            case "Selecionar Imagem":
                self.imagens = selecionar_arquivos()
                if self.imagens:
                    for imagem in self.imagens:
                        # self.query_one(Grid).style.display = "grid"
                        self.query_one(Grid).mount(
                            Image(imagem))
            case "Gerar Anúncio":
                if self.imagens:
                        mensagem = '''Gerar um TEXTO anúncio com titulo e descricao com base nas imagens. Ser profissional, não usar emojis e nao falar tanto sobre valores
                        Respeite esse formato:
                        
                        Titulo: "titulo do anuncio"
                        
                        Descrição: "descrição do anuncio"
                        
                        ATENÇÃO: A Imagem enviada é referente a um imóvel, então o anúncio deve ser sobre um imóvel, e deve ser um anúncio profissional, focado em vender ou alugar o imóvel.
                        '''

                        resposta = self.modelo_atual.enviar_mensagem(
                            mensagem=mensagem, imagens=self.imagens)
                        
                        
                        self.notify(resposta)
                        
                        try:

                            titulo = resposta.lower().split("titulo:")[1].strip()
                            descricao = resposta.lower().split("descrição:")[1].strip()

                            self.query_one("#titulo", Input).value = titulo
                            self.query_one("#descricao", Input).value = descricao

                        except Exception as e:
                            print(e)
                            self.notify(f"Não foi possível extrair o título e descrição do anúncio. Resposta: {resposta}")
                            self.query_one(TextArea).text = resposta
