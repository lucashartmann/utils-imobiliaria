import re
from textual.app import App
from textual_image.widget import Image
from textual.widgets import Button, Static, Input, ListItem, ListView
from textual.containers import Horizontal, Vertical, Center, Grid
import subprocess
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import tkinter as tk
from tkinter import filedialog


class App(App):
    CSS_PATH = "App.tcss"

    arquivos = [
        ("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff")
    ]
    caminho_mascara_selecionada = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.home = os.getcwd()
        if "Imagens" not in os.listdir():
            os.mkdir(self.home+"/Imagens")
        self.imagens_path = self.home + "\Imagens"
        if "Mascáras" not in os.listdir():
            os.mkdir(self.home+"/Mascáras")
        self.mascaras_path = self.home + "\Mascáras"
        if "Destino" not in os.listdir():
            os.mkdir(self.home+"/Destino")
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

    def compose(self):
        with Horizontal(id="header"):
            yield Static("Link do site:")
            yield Input(placeholder="link aqui")
            yield Button("Extrair")
            yield Button("Remover Logo")
            yield Button("Abrir Diretório")

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
                    yield Button("Limpar Imagens")
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
                imagens = self.selecionar_arquivo()
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
                        print(e)
                        continue

            case "Limpar Imagens":
                try:
                    primeiro_container.query_one(Image)
                except Exception as e:
                    print(e)
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
                    await worker.wait()
                    await self.converter()
                    self.carregar_imagens()
                    self.query_one(Input).value = ""
                except Exception as e:
                    self.notify(f"Erro! {e}")

            case "Remover Logo":
                try:
                    if self.caminho_mascara_selecionada:
                        self.pintagem(self.caminho_mascara_selecionada)
                        self.carregar_destino()
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
    #         print(texto)

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
    #         print(f"ERRO! gerar_mascara {e}")
    #         return None

    async def extracao(self, url):
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

            print(f"Encontradas {len(imagens)} imagens 1920px")

            for i, img_url in enumerate(imagens):
                try:
                    print("Baixando:", img_url)
                    img_data = requests.get(img_url, headers=headers).content
                    with open(f"{self.imagens_path}/img_{i}.jpg", "wb") as f:
                        f.write(img_data)
                except Exception as e:
                    print("Erro:", e)

        elif "zapimoveis" in url:
            imgs = soup.find_all("img")
            print(f"Encontradas {len(imgs)} tags <img> na página.")

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

                            print(f"Baixando {img_url} ...")
                            try:
                                img_data = requests.get(
                                    img_url, headers=headers).content
                                with open(save_path, "wb") as f:
                                    f.write(img_data)
                            except Exception as e:
                                print("Erro ao baixar:", e)
                                continue

    def pintagem(self, mascara):
        try:
            cmd = [
                "iopaint", "run",
                "--image", self.imagens_path,
                "--mask", mascara,
                "--output", self.destino_path,
            ]

            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        except Exception as e:
            print(e)

    async def converter(self):
        if len(os.listdir(self.imagens_path)) > 0:
            for arquivo in os.listdir(self.imagens_path):
                caminho = os.path.join(self.imagens_path, arquivo)
                nome, ext = os.path.splitext(arquivo)
                ext = ext.lower()

                if ext in ['.webp', '.avif']:
                    try:
                        with Image.open(caminho) as img:
                            png_path = os.path.join(
                                self.imagens_path, nome + '.png')
                            jpeg_path = os.path.join(
                                self.imagens_path, nome + '.jpg')
                            gif_path = os.path.join(
                                self.imagens_path, nome + '.gif')

                            if getattr(img, "is_animated", False):
                                frames = []
                                for frame in range(img.n_frames):
                                    img.seek(frame)
                                    frames.append(img.copy())
                                frames[0].save(
                                    gif_path,
                                    save_all=True,
                                    append_images=frames[1:],
                                    loop=0,
                                    duration=img.info.get("duration", 100)
                                )
                                novo_nome = gif_path
                            else:
                                if img.mode == 'RGBA':
                                    img = img.convert('RGB')
                                img.save(png_path, 'PNG')
                                img.save(jpeg_path, 'JPEG', quality=95)
                                png_size = os.path.getsize(png_path)
                                jpeg_size = os.path.getsize(jpeg_path)

                                if png_size >= jpeg_size:
                                    os.remove(jpeg_path)
                                    novo_nome = png_path
                                else:
                                    os.remove(png_path)
                                    novo_nome = jpeg_path

                            print(
                                f'Convertido: {arquivo} -> {os.path.basename(novo_nome)}')
                        os.remove(caminho)
                    except Exception as e:
                        print(f'Erro ao converter {arquivo}: {e}')

    def selecionar_arquivo(self):
        try:
            root = tk.Tk()
            root.withdraw()

            caminhos = filedialog.askopenfilenames(
                title="Selecione",
                filetypes=self.arquivos
            )

            caminhos = list(caminhos)

            root.destroy()
            return caminhos
        except Exception as e:
            print(e)
            pass
