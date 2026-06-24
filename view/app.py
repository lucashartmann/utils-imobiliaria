from uuid import uuid4
import os
from urllib.parse import urljoin
from view.anuncio import Anuncio
from utils.chavesnamao import extrair_imagens_chavesnamao
from utils.multiimob import extrair_imagens_multiimob, obter_html_renderizado_urban
from utils.zapimoveis import extrair_imagens_zapimoveis, obter_html_renderizado_zapimoveis
from utils.selecionar_arquivos import selecionar_arquivos
import re
import json
import requests
from bs4 import BeautifulSoup
import subprocess
from tkinter import messagebox
import shutil
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class App:

    arquivos = [
        ("Imagens", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff")
    ]

    caminho_mascara_selecionada = ""

    def __init__(self, root):

        self.root = root
        self.root.title("Removedor de Logos")

        self.home = os.getcwd()

        self.imagens_path = os.path.join(self.home, "Imagens")
        os.makedirs(self.imagens_path, exist_ok=True)

        self.mascaras_path = os.path.join(self.home, "Mascaras")
        os.makedirs(self.mascaras_path, exist_ok=True)

        self.destino_path = os.path.join(self.home, "Destino")
        os.makedirs(self.destino_path, exist_ok=True)

        self.thumbnails = []

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True)

        self.tab_imagens = tk.Frame(self.tabs)
        self.tab_anuncio = tk.Frame(self.tabs)

        self.tabs.add(self.tab_imagens, text="Imagens")
        self.tabs.add(self.tab_anuncio, text="Anúncio")

        self.tabs.bind(
            "<<NotebookTabChanged>>",
            self.on_tab_changed
        )

        header = tk.Frame(self.tab_imagens)
        header.pack(fill="x", padx=5, pady=5)

        tk.Label(
            header,
            text="Link do site:"
        ).pack(side="left")

        self.input_link = tk.Entry(header)

        self.input_link.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        tk.Button(
            header,
            text="Extrair",
            command=lambda: self.acao_botao("Extrair")
        ).pack(side="left")

        tk.Button(
            header,
            text="Remover Logo",
            command=lambda: self.acao_botao("Remover Logo")
        ).pack(side="left")

        tk.Button(
            header,
            text="Abrir Diretório",
            command=lambda: self.acao_botao("Abrir Diretório")
        ).pack(side="left")

        self.nome_pasta = tk.Entry(self.tab_imagens)

        self.nome_pasta.pack(
            fill="x",
            padx=5,
            pady=5
        )

        self.progress = ttk.Progressbar(
            self.tab_imagens,
            maximum=100
        )

        self.progress.pack(
            fill="x",
            padx=5,
            pady=5
        )

        conteudo = tk.Frame(self.tab_imagens)

        conteudo.pack(
            fill="both",
            expand=True
        )

        self.frame_antes = tk.LabelFrame(
            conteudo,
            text="Imagens"
        )

        self.frame_antes.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        self.grid_imagens_antes = tk.Frame(
            self.frame_antes
        )

        self.grid_imagens_antes.pack(
            fill="both",
            expand=True
        )

        botoes_antes = tk.Frame(
            self.frame_antes
        )

        botoes_antes.pack(
            fill="x",
            pady=5
        )

        tk.Button(
            botoes_antes,
            text="Escolher Imagens",
            command=lambda: self.acao_botao(
                "Escolher Imagens",
                self.grid_imagens_antes
            )
        ).pack(side="left", padx=5)

        tk.Button(
            botoes_antes,
            text="Limpar Imagens",
            command=lambda: self.acao_botao(
                "Limpar Imagens",
                self.grid_imagens_antes
            )
        ).pack(side="left", padx=5)

        self.frame_mascaras = tk.LabelFrame(
            conteudo,
            text="Máscaras"
        )

        self.frame_mascaras.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        self.lista_mascaras = tk.Listbox(
            self.frame_mascaras
        )

        self.lista_mascaras.pack(
            fill="both",
            expand=True
        )

        self.lista_mascaras.bind(
            "<<ListboxSelect>>",
            self.selecionar_mascara
        )

        botoes_mascaras = tk.Frame(
            self.frame_mascaras
        )

        botoes_mascaras.pack(
            fill="x",
            pady=5
        )

        tk.Button(
            botoes_mascaras,
            text="Escolher Imagens",
            command=lambda: self.acao_botao(
                "Escolher Imagens",
                self.lista_mascaras
            )
        ).pack(side="left", padx=5)

        tk.Button(
            botoes_mascaras,
            text="Atualizar Máscaras",
            command=lambda: self.acao_botao(
                "Atualizar Máscaras"
            )
        ).pack(side="left", padx=5)

        self.frame_depois = tk.LabelFrame(
            conteudo,
            text="Resultado"
        )

        self.frame_depois.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        self.grid_imagens_depois = tk.Frame(
            self.frame_depois
        )

        self.grid_imagens_depois.pack(
            fill="both",
            expand=True
        )

        botoes_depois = tk.Frame(
            self.frame_depois
        )

        botoes_depois.pack(
            fill="x",
            pady=5
        )

        tk.Button(
            botoes_depois,
            text="Escolher Imagens",
            command=lambda: self.acao_botao(
                "Escolher Imagens",
                self.grid_imagens_depois
            )
        ).pack(side="left", padx=5)

        tk.Button(
            botoes_depois,
            text="Limpar Imagens",
            command=lambda: self.acao_botao(
                "Limpar Imagens",
                self.grid_imagens_depois
            )
        ).pack(side="left", padx=5)

        self.carregar_imagens()
        self.carregar_mascaras()
        self.carregar_destino()

    def carregar_imagens(self):

        extensoes = (".jpg", ".jpeg", ".png")

        for arquivo in os.listdir(self.imagens_path):

            if arquivo.lower().endswith(extensoes):

                caminho = os.path.join(
                    self.imagens_path,
                    arquivo
                )

                self.adicionar_imagem(
                    self.frame_antes,
                    caminho
                )

    def carregar_mascaras(self):

        extensoes = (".jpg", ".jpeg", ".png")

        self.lista_mascaras.delete(
            0,
            tk.END
        )

        for arquivo in os.listdir(self.mascaras_path):

            if arquivo.lower().endswith(extensoes):

                caminho = os.path.join(
                    self.mascaras_path,
                    arquivo
                )

                self.lista_mascaras.insert(
                    tk.END,
                    caminho
                )

    def carregar_destino(self):

        extensoes = (".jpg", ".jpeg", ".png")

        for arquivo in os.listdir(self.destino_path):

            if arquivo.lower().endswith(extensoes):

                caminho = os.path.join(
                    self.destino_path,
                    arquivo
                )

                self.adicionar_imagem(
                    self.frame_depois,
                    caminho
                )


    def adicionar_imagem(self, frame, caminho):

        try:

            imagem = Image.open(caminho)

            imagem.thumbnail((150, 150))

            foto = ImageTk.PhotoImage(imagem)

            self.thumbnails.append(foto)

            label = tk.Label(
                frame,
                image=foto
            )

            label.image = foto

            label.pack(
                padx=5,
                pady=5
            )

        except Exception as e:
            print(e)

    def selecionar_mascara(self, event):

        selecionado = self.lista_mascaras.curselection()

        if not selecionado:
            return

        indice = selecionado[0]

        self.caminho_mascara_selecionada = (
            self.lista_mascaras.get(indice)
        )

    def on_tab_changed(self, event):

        indice = self.tabs.index(
            self.tabs.select()
        )

        if indice == 1:
            self.abrir_tela_anuncio()

    def acao_botao(self, acao, container=None):

        match acao:

            case "Atualizar Máscaras":

                self.lista_mascaras.delete(0, "end")

                for arquivo in os.listdir(self.mascaras_path):

                    if arquivo.lower().endswith((".jpg", ".jpeg", ".png")):

                        caminho = os.path.join(
                            self.mascaras_path,
                            arquivo
                        )

                        self.lista_mascaras.insert(
                            "end",
                            caminho
                        )

            case "Abrir Diretório":

                os.startfile(self.home)

            case "Escolher Imagens":

                imagens = selecionar_arquivos()

                if not imagens:
                    return

                if container == self.frame_antes:
                    destino = self.imagens_path

                elif container == self.frame_depois:
                    destino = self.destino_path

                elif container == self.lista_mascaras:
                    destino = self.mascaras_path

                else:
                    return

                for imagem in imagens:

                    try:

                        nome = os.path.basename(imagem)

                        shutil.copy2(
                            imagem,
                            os.path.join(destino, nome)
                        )

                        if container == self.lista_mascaras:

                            self.lista_mascaras.insert(
                                "end",
                                os.path.join(destino, nome)
                            )

                        else:

                            self.adicionar_imagem(
                                container,
                                imagem
                            )

                    except Exception as e:

                        messagebox.showerror(
                            "Erro",
                            f"Erro ao copiar imagem: {e}"
                        )

            case "Limpar Imagens":

                try:

                    destino = ""

                    if container == self.frame_antes:
                        destino = self.imagens_path

                    elif container == self.frame_depois:
                        destino = self.destino_path

                    else:
                        return

                    for widget in container.winfo_children():
                        widget.destroy()

                    for arquivo in os.listdir(destino):

                        caminho = os.path.join(
                            destino,
                            arquivo
                        )

                        if os.path.isfile(caminho):
                            os.remove(caminho)

                except Exception as e:

                    messagebox.showerror(
                        "Erro",
                        str(e)
                    )

            case "Extrair":

                link = self.input_link.get().strip()

                try:

                    threading.Thread(
                        target=self.extracao,
                        args=(link,),
                        daemon=True
                    ).start()

                    self.input_link.delete(
                        0,
                        "end"
                    )

                except Exception as e:

                    messagebox.showerror(
                        "Erro",
                        str(e)
                    )

            case "Remover Logo":

                try:

                    if not self.caminho_mascara_selecionada:

                        messagebox.showwarning(
                            "Aviso",
                            "Selecione uma máscara"
                        )

                        return

                    threading.Thread(
                        target=self.pintagem,
                        args=(self.caminho_mascara_selecionada,),
                        daemon=True
                    ).start()

                except Exception as e:

                    messagebox.showerror(
                        "Erro",
                        str(e)
                    )

    def selecionar_mascara(self, event):

        selecionado = self.lista_mascaras.curselection()

        if not selecionado:
            return

        indice = selecionado[0]

        self.caminho_mascara_selecionada = \
            self.lista_mascaras.get(indice)
    
    def extracao(self, url):

        def tarefa():

            self.root.after(0, lambda: self.resetar_progresso(0))

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            }

            try:

                response = requests.get(url, headers=headers)
                html = response.text

                soup = BeautifulSoup(html, "html.parser")

                nome_pasta = self.nome_pasta.get().strip()

                if nome_pasta:
                    imagens_path = os.path.join(self.imagens_path, nome_pasta)
                else:
                    imagens_path = self.imagens_path

                os.makedirs(imagens_path, exist_ok=True)

                if "urban.imb.br" in url:

                    html_renderizado = obter_html_renderizado_urban(url)

                    if html_renderizado:
                        html = html_renderizado
                        soup = BeautifulSoup(html, "html.parser")

                imagens = []

                if "auxiliadorapredial" in url:

                    pattern = r"https://img\.auxiliadorapredial\.com\.br/thumb/1920/[^\"']+\.jpg"

                    imagens = list(set(re.findall(pattern, html)))

                    total = len(imagens)

                    self.root.after(0, lambda: self.resetar_progresso(total))

                    for i, img_url in enumerate(imagens):

                        try:

                            self.root.after(
                                0,
                                lambda u=img_url: print(f"Baixando: {u}")
                            )

                            img_data = requests.get(img_url, headers=headers).content

                            img_path = os.path.join(imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )

                        except Exception as e:

                            self.root.after(
                                0,
                                lambda err=e: print(f"Erro: {err}")
                            )

                elif "creditoreal" in url:
            
                    def extrair_creditoreal(self, html, url):

                        soup = BeautifulSoup(html, "html.parser")
                        imagens = []

                        def normalizar(src: str) -> str:

                            src = src.strip().replace("\\/", "/")

                            if src.startswith("//"):
                                src = "https:" + src

                            elif src.startswith("/"):
                                src = urljoin(url, src)

                            return src

                        def valida(src: str) -> bool:

                            src_lower = src.lower()

                            if not any(ext in src_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                                return False

                            if "storage.googleapis.com/snapproperty_imgs/creditoreal/" in src_lower:
                                return True

                            return any(k in src_lower for k in ["imovel", "galeria", "foto"])

                        def adicionar(src: str):

                            if not src:
                                return

                            src = normalizar(src)

                            if valida(src) and src not in imagens:
                                imagens.append(src)

                        def extrair_base(src: str):

                            nome = os.path.basename(src.split("?", 1)[0])

                            match = re.match(
                                r"^(?P<base>.+?)(?:_(?P<tamanho>\d+))?\.(?:jpe?g|png|webp)$",
                                nome,
                                flags=re.IGNORECASE,
                            )

                            if not match:
                                return nome, 0

                            return match.group("base"), int(match.group("tamanho") or 0)

                        def melhores(urls):

                            melhores_dict = {}

                            for u in urls:

                                base, tamanho = extrair_base(u)

                                atual = melhores_dict.get(base)

                                if atual is None or tamanho > atual[0]:
                                    melhores_dict[base] = (tamanho, u)

                            return [v[1] for v in melhores_dict.values()]

                        script = soup.find("script", id="__NEXT_DATA__")

                        if script and script.string:

                            try:

                                dados = json.loads(script.string)

                                imgs = (
                                    dados.get("props", {})
                                    .get("pageProps", {})
                                    .get("imovel", {})
                                    .get("images", [])
                                )

                                urls = []

                                for item in imgs:

                                    if isinstance(item, dict):

                                        for k in ["src", "url", "imageUrl"]:

                                            if item.get(k):
                                                urls.append(normalizar(item[k]))

                                    elif isinstance(item, str):
                                        urls.append(normalizar(item))

                                urls_validas = [u for u in urls if valida(u)]

                                if urls_validas:
                                    return melhores(urls_validas)

                            except Exception:
                                pass

                        for img in soup.select('[aria-label="Zoom na imagem"] img'):
                            adicionar(img.get("src"))
                            adicionar(img.get("data-src"))

                        for img in soup.find_all("img"):

                            for attr in ["src", "data-src", "data-lazy", "data-original"]:
                                adicionar(img.get(attr))

                            if img.get("srcset"):

                                for parte in img.get("srcset").split(","):
                                    adicionar(parte.strip().split(" ")[0])

                        if len(imagens) < 3:

                            padrao = r'https?://storage\.googleapis\.com/snapproperty_imgs/creditoreal/[^"\s>]+?\.(?:jpe?g|png|webp)(?:\?[^"\s>]*)?'

                            imagens.extend(re.findall(padrao, html, flags=re.IGNORECASE))

                        return imagens
                    imagens = extrair_creditoreal(html, url)

                    total = len(imagens)

                    self.root.after(0, lambda: self.resetar_progresso(total))

                    for i, img_url in enumerate(imagens):

                        try:

                            print(f"Baixando: {img_url}")

                            img_data = requests.get(
                                img_url,
                                headers=headers,
                                timeout=10
                            ).content

                            img_path = os.path.join(
                                imagens_path,
                                f"img_{i}.jpg"
                            )

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )

                        except Exception as e:

                            print(f"Erro ao baixar: {e}")

                elif "chavesnamao" in url:
                    imagens = extrair_imagens_chavesnamao(html, url)

                    if not imagens:
                        print("Nenhuma imagem encontrada no Chaves na Mão")
                        return

                    print(f"Encontradas {len(imagens)} imagens")
                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(
                                img_url, headers=headers, timeout=10).content
                            img_path = os.path.join(imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )
                        except Exception as e:
                            print(f"Erro ao baixar: {e}")

                elif "multiimob.com.br" in url or "urban.imb.br" in url:
                    imagens = extrair_imagens_multiimob(html, url)

                    if not imagens:
                        print("Nenhuma imagem encontrada")
                        return

                    print(f"Encontradas {len(imagens)} imagens")
                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(
                                img_url, headers=headers, timeout=10).content
                            img_path = os.path.join(imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )
                        except Exception as e:
                            print(f"Erro ao baixar: {e}")

                elif "zapimoveis" in url:
                    html_renderizado = obter_html_renderizado_zapimoveis(url)
                    if html_renderizado:
                        html = html_renderizado
                        soup = BeautifulSoup(html, "html.parser")

                    imagens = extrair_imagens_zapimoveis(html, url)

                    if not imagens:
                        print("Nenhuma imagem encontrada no ZAP Imóveis")
                        return

                    print(f"Encontradas {len(imagens)} imagens")
                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    headers_zap = {
                        **headers,
                        "Referer": url,
                        "Origin": "https://www.zapimoveis.com.br",
                        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                    }

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            resp = requests.get(
                                img_url, headers=headers_zap, timeout=10)

                            if resp.status_code != 200:
                                print(
                                    f"Erro ao baixar imagem: HTTP {resp.status_code}"
                                )
                                continue

                            filename = f"img_{i}.jpg"

                            save_path = os.path.join(imagens_path, filename)

                            with open(save_path, "wb") as f:
                                f.write(resp.content)

                            self.root.after(
                                0,
                                lambda p=save_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )
                        except Exception as e:
                            print(f"Erro ao baixar: {e}")
                            continue
                elif "imobiliariazimmer" in url:
                    match = re.search(r"/(\d+)/", url)
                    if not match:
                        print("ID do imóvel não encontrado")
                        return

                    imovel_id = match.group(1)

                    api = f"https://imobiliariazimmer.com.br/Services/RealEstate/JSONP/List.aspx?mode=realty&nt=2&ri={imovel_id}"

                    resp = requests.get(api, headers=headers)
                    data = resp.text

                    pattern = r"https://inetsoft\.imobiliariazimmer\.com\.br/Fotos/[^\"]+\.jpg"
                    imagens = re.findall(pattern, data)

                    imagens = list(set(imagens))

                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    print(f"Encontradas {len(imagens)} imagens")

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")

                            img_data = requests.get(img_url, headers=headers).content

                            img_path = os.path.join(imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )

                        except Exception as e:
                            print(f"Erro: {e}")

                elif 'veronezimoveis.com.br' in url:
                    id_match = re.search(r"/imovel/(\d+)/", url)
                    if not id_match:
                        print("ID do imóvel não encontrado")
                        return

                    imovel_id = id_match.group(1)

                    imagens = list(dict.fromkeys(
                        re.findall(
                            r"https://www\.veronezimoveis\.com\.br/media/imoveis/[^\"'\s>]+?\.(?:jpe?g|png|webp)",
                            html,
                            flags=re.IGNORECASE,
                        )
                    ))

                    if not imagens:
                        print("Nenhuma imagem encontrada na página")
                        return

                    imagens = list(set(imagens))
                    print(f"Encontradas {len(imagens)} imagens")
                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))
                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(img_url, headers=headers).content
                            img_path = os.path.join(imagens_path, f"img_{i}.jpg")
                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )
                        except Exception as e:
                            print(f"Erro ao baixar: {e}")
                            continue

                elif "quintoandar.com.br" in url:

                    id_match = re.search(r"/imovel/(\d+)/", url)
                    if not id_match:
                        print("ID do imóvel não encontrado")
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
                                if url_img.startswith("/"):
                                    url_img = "https://www.quintoandar.com.br" + url_img
                                elif not url_img.startswith("http"):
                                    url_img = "https://www.quintoandar.com.br/img/" + url_img
                                imagens.append(url_img)

                    imagens = list(dict.fromkeys(imagens))

                    print(f"{len(imagens)} imagens encontradas")

                    for i, img_url in enumerate(imagens):
                        try:
                            resp = requests.get(img_url, headers=headers, timeout=10)

                            if resp.status_code != 200:
                                print(f"Erro {resp.status_code}: {img_url}")
                                continue

                            nome_arquivo = f"img_{i}.jpg"

                            img_path = os.path.join(imagens_path, nome_arquivo)

                            with open(img_path, "wb") as f:
                                f.write(resp.content)

                            self.root.after(
                                0,
                                lambda p=img_path: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )

                        except Exception as e:
                            print(f"Erro ao baixar {img_url}: {e}")

                elif "guarida.com.br" in url:
                    imovel_id_match = re.search(r"/(\d+)(?:\?|$)", url)
                    if not imovel_id_match:
                        print("ID do imóvel não encontrado")
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

                    print(f"Encontradas {len(imagens)} imagens")

                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            resp = requests.get(img_url, headers=headers, timeout=10)

                            if resp.status_code != 200:
                                continue

                            nome = f"img_{i}.jpg"
                            caminho = f"{imagens_path}/{nome}"

                            with open(caminho, "wb") as f:
                                f.write(resp.content)

                            self.root.after(
                                0,
                                lambda p=caminho: self._adicionar_imagem_na_ui(p)
                            )

                            self.root.after(
                                0,
                                lambda: self.avancar_progresso(1)
                            )

                        except Exception as e:
                            print(f"Erro: {e}")

                elif "foxterciaimobiliaria.com.br" in url:
                    def _foxter_url_alta_resolucao(img_url: str) -> str:
                        if img_url.startswith("http"):
                            if "/foxter/wm/" in img_url:
                                caminho = img_url.split("/foxter/wm/", 1)[1]
                                return f"https://blob.foxter.com.br/rest/image/outer/1920/1/foxter/wm/{caminho}"

                            return (
                                re.sub(r"/outer/\d+/", "/outer/1920/", img_url, count=1)
                                .replace("https://images.foxter.com.br", "https://blob.foxter.com.br")
                            )

                        return f"https://blob.foxter.com.br/rest/image/outer/1920/1/foxter/wm/{img_url.lstrip('/')}"

                    imagens = []
                    try:
                        dados_next = json.loads(
                            re.search(
                                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                                html,
                            ).group(1)
                        )
                        produto = dados_next["props"]["pageProps"]["product"]
                        imagens_data = produto.get("images", {}).get("data", [])

                        imagens = [
                            _foxter_url_alta_resolucao(item["etag"])
                            for item in imagens_data
                            if item.get("etag")
                        ]
                    except Exception:
                        pattern = r"https://images\.foxter\.com\.br/[^\s\"']+\.jpg"
                        imagens_brutas = list(dict.fromkeys(re.findall(pattern, html)))
                        imagens = [
                            _foxter_url_alta_resolucao(img_url)
                            for img_url in imagens_brutas
                        ]

                    print(f"Encontradas {len(imagens)} imagens")

                    headers_img = {
                        "User-Agent": headers["User-Agent"],
                        "Referer": "https://www.foxterciaimobiliaria.com.br/"
                    }

                    self.root.after(0, lambda: self.resetar_progresso(len(imagens)))

                    for i, url in enumerate(imagens):
                        try:
                            print(f"Baixando: {url}")

                            # if worker.is_cancelled:
                            #     return

                            resp = requests.get(url, headers=headers_img, timeout=10)

                            if resp.status_code == 200:
                                img_path = os.path.join(
                                    imagens_path, f"img_{i}.jpg")

                                with open(img_path, "wb") as f:
                                    f.write(resp.content)

                                self.root.after(
                                    0,
                                    lambda p=img_path: self._adicionar_imagem_na_ui(p)
                                )

                                self.root.after(
                                    0,
                                    lambda: self.avancar_progresso(1)
                                )

                            else:
                                print(
                                    f"Erro ao baixar imagem: HTTP {resp.status_code}")

                        except Exception as e:
                            print(f"Erro ao baixar imagem: {e}")
            
            except Exception as e:

                self.root.after(
                    0,
                    lambda: print(f"Erro geral: {e}")
                )

        threading.Thread(target=tarefa, daemon=True).start()

    def adicionar_imagem_na_ui(self, caminho_imagem: str):

        try:

            if not os.path.exists(caminho_imagem):

                messagebox.showerror(
                    "Erro",
                    f"Arquivo não encontrado: {caminho_imagem}"
                )

                return

            self.adicionar_imagem(
                self.grid_imagens_antes,
                caminho_imagem
            )

        except Exception as e:

            messagebox.showerror(
                "Erro",
                f"Erro ao adicionar imagem na UI: {e}"
            )


    def resetar_progresso(self, total: int):

        self.progress["maximum"] = total
        self.progress["value"] = 0

        self.root.update_idletasks()


    def avancar_progresso(self, passos: int = 1):

        self.progress["value"] += passos

        self.root.update_idletasks()

    def pintagem(self, mascara):

        def tarefa():

            etapas_total = 5

            try:

                self.root.after(0, lambda: self.resetar_progresso(etapas_total))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Info",
                    "Iniciando remoção de logo..."
                ))

                imagens_path = os.path.join(self.home, "Imagens")
                destino_path = os.path.join(self.home, "Destino")

                arquivos = os.listdir(imagens_path)

                if len(arquivos) == 0:

                    cmd = [
                        "iopaint", "run",
                        "--image", imagens_path,
                        "--mask", mascara,
                        "--output", destino_path,
                    ]

                    self.root.after(0, lambda: self.avancar_progresso(1))

                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    self.root.after(0, lambda: self.avancar_progresso(1))

                    stdout, stderr = process.communicate()

                    self.root.after(0, lambda: self.avancar_progresso(1))

                    if stdout and stdout.strip():

                        for linha in stdout.splitlines()[-3:]:

                            self.root.after(
                                0,
                                lambda l=linha: print(f"iopaint: {l}")
                            )

                    if stderr and stderr.strip():

                        for linha in stderr.splitlines()[-3:]:

                            self.root.after(
                                0,
                                lambda l=linha: print(f"iopaint stderr: {l}")
                            )

                    if process.returncode == 0:

                        self.root.after(
                            0,
                            lambda: messagebox.showinfo(
                                "Sucesso",
                                "Remoção de logo concluída com sucesso"
                            )
                        )

                        self.root.after(
                            0,
                            self.carregar_destino
                        )

                    else:

                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Erro",
                                f"Falha ao remover logo ({process.returncode})"
                            )
                        )

                    self.root.after(0, lambda: self.avancar_progresso(2))

                else:

                    for pasta in arquivos:

                        pasta_imagem = os.path.join(imagens_path, pasta)
                        destino = os.path.join(destino_path, pasta)

                        cmd = [
                            "iopaint", "run",
                            "--image", pasta_imagem,
                            "--mask", mascara,
                            "--output", destino,
                        ]

                        self.root.after(0, lambda c=cmd: print("Executando:", " ".join(c)))

                        self.root.after(0, lambda: self.avancar_progresso(1))

                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )

                        self.root.after(0, lambda: self.avancar_progresso(1))

                        stdout, stderr = process.communicate()

                        self.root.after(0, lambda: self.avancar_progresso(1))

                        if process.returncode == 0:

                            self.root.after(
                                0,
                                lambda: messagebox.showinfo(
                                    "Sucesso",
                                    "Remoção de logo concluída com sucesso"
                                )
                            )

                            self.root.after(0, self.carregar_destino)

                        else:

                            self.root.after(
                                0,
                                lambda c=process.returncode: messagebox.showerror(
                                    "Erro",
                                    f"Falha ao remover logo ({c})"
                                )
                            )

                        self.root.after(0, lambda: self.avancar_progresso(2))

            except Exception as e:

                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Erro",
                        f"Erro na pintagem: {e}"
                    )
                )

        threading.Thread(target=tarefa, daemon=True).start()
        
        
    def run(self):
        self.root.mainloop()
    
if __name__ == "__main__":

    root = tk.Tk()
    root.geometry("1000x700")

    app = App(root)

    root.mainloop()