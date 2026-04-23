import re
from textual.app import App
from textual_image.widget import Image
from textual.widgets import Button, Static, Input, ListItem, ListView, ProgressBar, TabbedContent, TabPane, Tab, Tabs
from textual.containers import Horizontal, Vertical, Center, Grid
import subprocess
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from textual.worker import get_current_worker
from textual.renderables.bar import Bar as BarRenderable
from view.anuncio import Anuncio
from utils.selecionar_arquivos import selecionar_arquivos


class App(App):
    CSS_PATH = ["css/base.tcss", "css/app.tcss"]

    SCREENS = {
        "anuncio": Anuncio
    }

    arquivos = [
        ("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff")
    ]

    BINDINGS = [
        ("cntrl+q", "sair", "Sair"),
    ]

    def action_sair(self):
        for worker in self.workers:
            worker.stop()
        self.exit()

    caminho_mascara_selecionada = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.home = os.getcwd()
        if "Imagens" not in os.listdir():
            os.mkdir(self.home+"/imagens")
        self.imagens_path = self.home + "\Imagens"
        if "Mascáras" not in os.listdir():
            os.mkdir(self.home+"/mascáras")
        self.mascaras_path = self.home + "\Mascáras"
        if "Destino" not in os.listdir():
            os.mkdir(self.home+"/destino")
        self.destino_path = self.home + "\Destino"

    def on_mount(self):
        self.carregar_imagens()
        if len(os.listdir(self.mascaras_path)) > 0:
            for caminho_imagem in os.listdir(self.mascaras_path):
                if caminho_imagem.split(".")[-1] in ["jpg", "jpeg", "png"]:
                    self.query_one("#lv_mascaras").mount(ListItem(
                        Image(f"{self.mascaras_path}\\{caminho_imagem}"), Static(caminho_imagem)))

        self.carregar_destino()

    def carregar_imagens(self):
        if len(os.listdir(self.imagens_path)) > 0:
            for caminho_imagem in os.listdir(self.imagens_path):
                if caminho_imagem.split(".")[-1] in ["jpg", "jpeg", "png"]:
                    self.query_one("#grid_imagens_antes").mount(
                        Image(f"{self.imagens_path}\\{caminho_imagem}"))

    def carregar_destino(self):
        if len(os.listdir(self.destino_path)) > 0:
            for caminho_imagem in os.listdir(self.destino_path):
                if caminho_imagem.split(".")[-1] in ["jpg", "jpeg", "png"]:
                    self.query_one("#grid_imagens_depois").mount(
                        Image(f"{self.destino_path}\\{caminho_imagem}"))

    def on_screen_resume(self):
        self.query_one(Tabs).active = self.query_one(
            "#tab_imagens", Tab).id

    def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        if event.tabs.active == self.query_one("#tab_anuncio", Tab).id:
            self.app.push_screen("anuncio")

    def compose(self):
        yield Tabs(Tab('Imagens', id="tab_imagens"), Tab("Anúncio", id="tab_anuncio"))

        with Horizontal(id="header"):
            yield Static("Link do site:")
            yield Input(placeholder="link aqui")
            yield Button("Extrair")
            yield Button("Remover Logo")
            yield Button("Abrir Diretório")

        yield ProgressBar(id="progress", total=100, show_percentage=True)

        with Horizontal(id="conteudo"):
            with Vertical(classes="imagens"):
                # Imagens
                yield Grid(id="grid_imagens_antes", classes="sub_imagens")
                with Center():
                    yield Button("Escolher Imagens")
                    yield Button("Limpar Imagens")
            with Vertical(classes="imagens"):
                # Mascaras
                yield ListView(id="lv_mascaras", classes="sub_imagens")
                with Center():
                    yield Button("Escolher Imagens")
                    # yield Button("Limpar Imagens")
            with Vertical(classes="imagens"):
                # Imagens sem mascara
                yield Grid(id="grid_imagens_depois", classes="sub_imagens")
                with Center():
                    yield Button("Escolher Imagens")
                    yield Button("Limpar Imagens")

    async def on_button_pressed(self, evento: Button.Pressed):
        center = evento.button.parent
        vertical = center.parent
        primeiro_container = list(vertical.children)[0]
        match evento.button.label:
            case "Abrir Diretório":
                os.startfile(self.home)

            case "Escolher Imagens":
                imagens = selecionar_arquivos()
                caminho = ""
                match primeiro_container.id:
                    case "grid_imagens_depois":
                        caminho = self.destino_path
                    case "lv_mascaras":
                        caminho = self.mascaras_path
                    case "grid_imagens_antes":
                        caminho = self.imagens_path

                for imagem in imagens:
                    try:
                        primeiro_container.mount(Image(imagem))
                        with open(imagem, "rb") as f:
                            data = f.read()
                        nome_arquivo = os.path.basename(imagem)
                        with open(os.path.join(caminho, nome_arquivo), "wb") as f:
                            f.write(data)
                    except Exception as e:
                        self.notify(f"Erro ao copiar imagem: {e}")
                        continue

            case "Limpar Imagens":
                try:
                    primeiro_container.query_one(Image)
                except Exception as e:
                    self.notify(f"Erro ao limpar imagens: {e}")
                    return
                for widget_imagem in primeiro_container.query(Image):
                    os.remove(widget_imagem.image)
                    widget_imagem.remove()

            case "Extrair":
                link = self.query_one(Input).value
                try:
                    worker = self.run_worker(
                        self.extracao(link),
                        name="Extraindo imagens",
                        thread=True,
                        exclusive=True,
                    )
                    # await worker.wait()
                    # await self.converter()
                    self.query_one(Input).value = ""
                except Exception as e:
                    self.notify(f"Erro! {e}")

            case "Remover Logo":
                try:
                    if self.caminho_mascara_selecionada:
                        self.run_worker(
                            lambda: self.pintagem(self.caminho_mascara_selecionada),
                            name="Removendo logo",
                            thread=True,
                            exclusive=True,
                        )
                    else:
                        self.notify("Selecione uma máscara")
                except Exception as e:
                    self.notify(f"Erro! {e}")

    def on_list_view_selected(self, evento: ListView.Selected):
        list_item = evento.item
        caminho = list_item.query_one(Image).image
        self.caminho_mascara_selecionada = caminho

    # def gerar_mascara(caminho_image, caminho_saida="mask.png"):
    #     try:
    #         prompt = """
    #         Identifique a logo na imagem.
    #         Retorne apenas um JSON no formato:
    #         {"x": int, "y": int, "width": int, "height": int}
    #         Não escreva mais nada além do JSON.
    #         """

    #         resposta = ollama.chat(
    #             model="llava:7b",
    #             messages=[
    #                 {
    #                     "role": "user",
    #                     "content": prompt,
    #                     "images": [caminho_image]
    #                 }
    #             ]
    #         )

    #         texto = resposta.message.content.strip()
    #         if texto.startswith("```"):
    #             texto = texto.split("```")[1]
    #         if texto.startswith("json"):
    #             texto = texto.split("json")[1]

    #         if "{" in texto:
    #             texto = texto.split("{")[1]
    #         texto = "{" + texto.strip()
    #         self.notify(texto)

    #         dados = json.loads(texto)

    #         x = 0.417
    #         y = 0.698
    #         w = 0.583
    #         h = 0.295

    #         imagem = cv2.imread(caminho_image)
    #         altura, largura = imagem.shape[:2]

    #         mascara = np.zeros((altura, largura), dtype=np.uint8)
    #         mascara[y:y+h, x:x+w] = 255

    #         cv2.imwrite(caminho_saida, mascara)

    #         return caminho_saida

    #     except Exception as e:
    #         self.notify(f"ERRO! gerar_mascara {e}")
    #         return None

    async def extracao(self, url):
        self.query_one("#progress").total = 0
        worker = get_current_worker()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        os.makedirs(self.imagens_path, exist_ok=True)

        if "auxiliadorapredial" in url:
            pattern = r"https://img\.auxiliadorapredial\.com\.br/thumb/1920/[^\"']+\.jpg"

            imagens = re.findall(pattern, html)

            imagens = list(set(imagens))

            self.query_one("#progress").total = len(imagens)

            self.notify(f"Encontradas {len(imagens)} imagens 1920px")

            for i, img_url in enumerate(imagens):
                try:
                    self.notify(f"Baixando: {img_url}")
                    img_data = requests.get(img_url, headers=headers).content
                    img_path = os.path.join(self.imagens_path, f"img_{i}.jpg")
                    with open(img_path, "wb") as f:
                        f.write(img_data)

                    self.call_from_thread(
                        self._adicionar_imagem_na_ui,
                        f"img_{i}.jpg"
                    )

                    self.query_one("#progress").advance(1)
                except Exception as e:
                    self.notify(f"Erro: {e}")

        elif "zapimoveis" in url:
            imgs = soup.find_all("img")
            self.notify(f"Encontradas {len(imgs)} tags <img> na página.")
            self.query_one("#progress").total = len(imgs)
            for img in imgs:
                srcset = img.get("srcset")
                if srcset:
                    parts = srcset.split(",")
                    for part in parts:
                        part = part.strip()
                        if "1080w" in part:
                            img_url = part.split(" ")[0]
                            img_url = urljoin(url, img_url)

                            filename = img_url.split("/")[-1].split("?")[0]
                            save_path = os.path.join(
                                self.imagens_path, filename)

                            self.notify(f"Baixando {img_url} ...")
                            try:
                                img_data = requests.get(
                                    img_url, headers=headers).content
                                with open(save_path, "wb") as f:
                                    f.write(img_data)

                                self.call_from_thread(
                                    self._adicionar_imagem_na_ui,
                                    save_path
                                )

                                self.query_one("#progress").advance(1)
                            except Exception as e:
                                self.notify(f"Erro ao baixar: {e}")
                                continue
        elif "imobiliariazimmer" in url:
            match = re.search(r"/(\d+)/", url)
            if not match:
                self.notify("ID do imóvel não encontrado")
                return

            imovel_id = match.group(1)

            api = f"https://imobiliariazimmer.com.br/Services/RealEstate/JSONP/List.aspx?mode=realty&nt=2&ri={imovel_id}"

            resp = requests.get(api, headers=headers)
            data = resp.text

            pattern = r"https://inetsoft\.imobiliariazimmer\.com\.br/Fotos/[^\"]+\.jpg"
            imagens = re.findall(pattern, data)

            imagens = list(set(imagens))

            self.query_one("#progress").total = len(imagens)

            self.notify(f"Encontradas {len(imagens)} imagens")

            for i, img_url in enumerate(imagens):
                try:
                    self.notify(f"Baixando: {img_url}")

                    img_data = requests.get(img_url, headers=headers).content

                    img_path = os.path.join(self.imagens_path, f"img_{i}.jpg")

                    with open(img_path, "wb") as f:
                        f.write(img_data)

                    self.call_from_thread(
                        self._adicionar_imagem_na_ui,
                        img_path
                    )

                    self.query_one("#progress").advance(1)

                except Exception as e:
                    self.notify(f"Erro: {e}")

        elif "quintoandar.com.br" in url:
            id_match = re.search(r"/imovel/(\d+)/", url)
            if not id_match:
                self.notify("ID do imóvel não encontrado")
                return

            imovel_id = id_match.group(1)

            api_url = f"https://www.quintoandar.com.br/property/{imovel_id}/photos?variant=0"

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": f"https://www.quintoandar.com.br/imovel/{imovel_id}",
                "Origin": "https://www.quintoandar.com.br"
            }

            resp = requests.get(api_url, headers=headers)
            data = resp.json()

            imagens = []

            for foto in data:
                if isinstance(foto, dict):
                    url_img = foto.get("url") or foto.get(
                        "imageUrl") or foto.get("src")

                    if url_img:
                        # if "original" in url_img:
                        #     url_img = url_img.replace("original", "1280x1280")
                        if url_img.startswith("/"):
                            url_img = "https://www.quintoandar.com.br" + url_img
                        elif not url_img.startswith("http"):
                            url_img = "https://www.quintoandar.com.br/img/" + url_img
                        imagens.append(url_img)

            imagens_unicas = {}
            for img_url in imagens:
                match = re.search(r"(MG\d+\.jpg)", img_url)
                if match:
                    imagens_unicas[match.group(1)] = img_url

            imagens = list(imagens_unicas.values())

            self.notify(f"{len(imagens)} imagens encontradas")

            for i, img_url in enumerate(imagens):
                try:
                    resp = requests.get(img_url, headers=headers, timeout=10)

                    if resp.status_code != 200:
                        self.notify(f"Erro {resp.status_code}: {img_url}")
                        continue

                    nome_arquivo = f"img_{i}.jpg"

                    img_path = os.path.join(self.imagens_path, nome_arquivo)

                    with open(img_path, "wb") as f:
                        f.write(resp.content)

                    self.call_from_thread(
                        self._adicionar_imagem_na_ui,
                        img_path
                    )

                    self.query_one("#progress").advance(1)

                except Exception as e:
                    self.notify(f"Erro ao baixar {img_url}: {e}")

        elif "guarida.com.br" in url:
            imovel_id_match = re.search(r"/(\d+)(?:\?|$)", url)
            if not imovel_id_match:
                self.notify("ID do imóvel não encontrado")
                return

            imovel_id = imovel_id_match.group(1)

            resp = requests.get(url, headers=headers)
            html = resp.text

            imagens_brutas = re.findall(
                rf"https:(?:\\/|/)(?:\\/|/)cdn\.imoview\.com\.br(?:\\/|/)guarida(?:\\/|/)Imoveis(?:\\/|/){imovel_id}(?:\\/|/)[^\"'\s]+?\.(?:jpe?g|png|webp)(?:\?[^\"'\s]*)?",
                html,
                flags=re.IGNORECASE,
            )
            imagens = list(dict.fromkeys(
                img.replace("\\/", "/").replace("\\u0026", "&")
                for img in imagens_brutas
            ))

            self.notify(f"Encontradas {len(imagens)} imagens")

            self.query_one("#progress").total = len(imagens)

            for i, img_url in enumerate(imagens):
                try:
                    resp = requests.get(img_url, headers=headers, timeout=10)

                    if resp.status_code != 200:
                        continue

                    nome = f"img_{i}.jpg"
                    caminho = f"{self.imagens_path}/{nome}"

                    with open(caminho, "wb") as f:
                        f.write(resp.content)

                    self.call_from_thread(
                        self._adicionar_imagem_na_ui,
                        caminho
                    )

                    self.query_one("#progress").advance(1)

                except Exception as e:
                    self.notify(f"Erro: {e}")

        elif "foxterciaimobiliaria.com.br" in url:
            pattern = r"https://images\.foxter\.com\.br/[^\s\"']+\.jpg"
            imagens = list(set(re.findall(pattern, html)))

            self.notify(f"Encontradas {len(imagens)} imagens")

            headers_img = {
                "User-Agent": headers["User-Agent"],
                "Referer": "https://www.foxterciaimobiliaria.com.br/"
            }

            self.query_one("#progress").total = len(imagens)

            for i, url in enumerate(imagens):
                try:
                    self.notify(f"Baixando: {url}")

                    # if worker.is_cancelled:
                    #     return

                    resp = requests.get(url, headers=headers_img, timeout=10)

                    if resp.status_code == 200:
                        img_path = os.path.join(
                            self.imagens_path, f"img_{i}.jpg")

                        with open(img_path, "wb") as f:
                            f.write(resp.content)

                        self.call_from_thread(
                            self._adicionar_imagem_na_ui,
                            img_path
                        )

                        self.query_one("#progress").advance(1)

                    else:
                        self.notify(
                            f"Erro ao baixar imagem: HTTP {resp.status_code}")

                except Exception as e:
                    self.notify(f"Erro ao baixar imagem: {e}")

    def _adicionar_imagem_na_ui(self, caminho_imagem: str):
        try:
            if not os.path.exists(caminho_imagem):
                self.notify(f"Arquivo não encontrado: {caminho_imagem}")
                return
            self.query_one("#grid_imagens_antes").mount(
                Image(caminho_imagem))
        except Exception as e:
            self.notify(f"Erro ao adicionar imagem na UI: {e}")

    def _resetar_progresso(self, total: int):
        progress = self.query_one("#progress")
        progress.update(total=total, progress=0)

    def _avancar_progresso(self, passos: int = 1):
        self.query_one("#progress").advance(passos)

    def pintagem(self, mascara):
        etapas_total = 5
        try:
            self.call_from_thread(self._resetar_progresso, etapas_total)
            self.call_from_thread(self.notify, "Iniciando remoção de logo...")

            cmd = [
                "iopaint", "run",
                "--image", self.imagens_path,
                "--mask", mascara,
                "--output", self.destino_path,
            ]
            self.call_from_thread(self.notify, f"Executando: {' '.join(cmd)}")
            self.call_from_thread(self._avancar_progresso, 1)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.call_from_thread(self._avancar_progresso, 1)

            stdout, stderr = process.communicate()
            self.call_from_thread(self._avancar_progresso, 1)

            if stdout and stdout.strip():
                for linha in stdout.splitlines()[-3:]:
                    self.call_from_thread(self.notify, f"iopaint: {linha}")

            if stderr and stderr.strip():
                for linha in stderr.splitlines()[-3:]:
                    self.call_from_thread(self.notify, f"iopaint stderr: {linha}")

            if process.returncode == 0:
                self.call_from_thread(self.notify, "Remoção de logo concluída com sucesso")
                self.call_from_thread(self.carregar_destino)
            else:
                self.call_from_thread(
                    self.notify,
                    f"Falha ao remover logo (código {process.returncode})"
                )

            self.call_from_thread(self._avancar_progresso, 2)

        except Exception as e:
            self.call_from_thread(self.notify, f"Erro na pintagem: {e}")
