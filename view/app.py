from uuid import uuid4
import os
from urllib.parse import urljoin
try:
    from view.anuncio import AnuncioApp
    from view.pintarImagem import LogoPainterApp
except ImportError:
    from anuncio import AnuncioApp
    from pintarImagem import LogoPainterApp
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
from PIL import Image, ImageDraw, ImageTk

import argparse
import io
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from typing import Optional
import tkinter.font as tkfont


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif")


def _criar_icone_pasta(size: int = 16):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((1, 6, size - 2, size - 2), fill="#f0c04a", outline="#b8871b")
    draw.rectangle((2, 3, size // 2 + 3, 7), fill="#f5d77a", outline="#b8871b")
    return ImageTk.PhotoImage(img)


def _criar_icone_arquivo(size: int = 16):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((2, 1, size - 3, size - 2), fill="#ffffff", outline="#8a8a8a")
    draw.polygon([(size - 6, 1), (size - 3, 1), (size - 3, 4)], fill="#dadada", outline="#8a8a8a")
    draw.line((4, 6, size - 5, 6), fill="#9a9a9a")
    draw.line((4, 9, size - 5, 9), fill="#9a9a9a")
    return ImageTk.PhotoImage(img)


class NavegadorArquivos(tk.Frame):
    def __init__(self, parent, raiz: str, extensoes=IMAGE_EXTENSIONS, titulo: str = "", multisselecao: bool = True):
        super().__init__(parent)
        self.raiz = Path(raiz).resolve()
        self.extensoes = tuple(extensoes)
        self.titulo = titulo
        self.multisselecao = multisselecao
        self._icone_pasta = _criar_icone_pasta()
        self._thumb_tamanho = 72
        self._thumb_cache = {}
        self._file_nodes = {}
        self._drag_item = None
        self._drag_overlay = None
        self._style = ttk.Style(self)
        self._style.configure("Browser.Treeview", rowheight=self._thumb_tamanho + 16)

        self._build_ui()
        self.recarregar()

    def _build_ui(self):
        if self.titulo:
            tk.Label(self, text=self.titulo, anchor="w", font=("", 10, "bold")).pack(fill="x", padx=8, pady=(4, 2))

        barra = tk.Frame(self)
        barra.pack(fill="x", padx=4, pady=(0, 4))
        self._caminho_var = tk.StringVar(value=str(self.raiz))
        tk.Entry(barra, textvariable=self._caminho_var).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(barra, text="Ir", width=4, command=self._ir_para_raiz).pack(side="left")
        tk.Button(barra, text="P", width=2, command=lambda: self._set_thumb_size(32)).pack(side="left", padx=(6, 2))
        tk.Button(barra, text="M", width=2, command=lambda: self._set_thumb_size(72)).pack(side="left", padx=2)
        tk.Button(barra, text="G", width=2, command=lambda: self._set_thumb_size(112)).pack(side="left", padx=2)

        self._scroll = tk.Scrollbar(self, orient="vertical")
        self._scroll.pack(side="right", fill="y")

        selectmode = "extended" if self.multisselecao else "browse"
        self.tree = ttk.Treeview(self, show="tree", selectmode=selectmode, yscrollcommand=self._scroll.set, style="Browser.Treeview")
        self.tree.pack(fill="both", expand=True)
        self._scroll.config(command=self.tree.yview)

        self.tree.bind("<<TreeviewOpen>>", self._expandir_no)
        self.tree.bind("<Double-1>", self._alternar_no)
        self.tree.bind("<Button-3>", self._abrir_menu_contexto)
        self.tree.bind("<ButtonPress-1>", self._iniciar_drag)
        self.tree.bind("<B1-Motion>", self._arrastar_item)
        self.tree.bind("<ButtonRelease-1>", self._soltar_item)

    def _ir_para_raiz(self):
        caminho = Path(self._caminho_var.get()).expanduser().resolve()
        if caminho.is_dir():
            self.raiz = caminho
            self.recarregar()
        else:
            messagebox.showerror("Erro", f"Pasta não encontrada: {caminho}")

    def recarregar(self):
        self.tree.delete(*self.tree.get_children())
        self._thumb_cache.clear()
        self._file_nodes.clear()
        if not self.raiz.exists():
            return

        nome_raiz = self.raiz.name or str(self.raiz)
        self._node_raiz = self.tree.insert("", "end", text=nome_raiz, image=self._icone_pasta, open=True, values=(str(self.raiz), "dir"))
        self._tree_adicionar_filhos(self._node_raiz, self.raiz)
        self.tree.item(self._node_raiz, open=True)

    def _tree_adicionar_filhos(self, parent, pasta: Path):
        try:
            filhos = sorted(pasta.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except Exception:
            return

        for filho in filhos:
            if filho.is_dir():
                no = self.tree.insert(parent, "end", text=filho.name, image=self._icone_pasta, open=False, values=(str(filho), "dir"))
                self.tree.insert(no, "end", text="...", values=(str(filho), "placeholder"))
            elif filho.is_file() and filho.suffix.lower() in self.extensoes:
                thumb = self._carregar_miniatura(filho)
                no = self.tree.insert(parent, "end", text=filho.name, image=thumb, values=(str(filho), "file"))
                self._file_nodes[str(filho.resolve())] = no

    def _set_thumb_size(self, tamanho: int):
        self._thumb_tamanho = max(24, min(192, int(tamanho)))
        self._style.configure("Browser.Treeview", rowheight=self._thumb_tamanho + 16)
        self.recarregar()

    def aplicar_zoom_interface(self, fator: float):
        rowheight = max(18, int(round((self._thumb_tamanho + 16) * fator)))
        self._style.configure("Browser.Treeview", rowheight=rowheight)

    def _carregar_miniatura(self, caminho: Path):
        chave = (str(caminho.resolve()), self._thumb_tamanho)
        thumb = self._thumb_cache.get(chave)
        if thumb is not None:
            return thumb

        try:
            imagem = Image.open(caminho)
            imagem.thumbnail((self._thumb_tamanho, self._thumb_tamanho))
            thumb = ImageTk.PhotoImage(imagem)
        except Exception:
            thumb = _criar_icone_arquivo(max(16, self._thumb_tamanho // 2))

        self._thumb_cache[chave] = thumb
        return thumb

    def _expandir_no(self, event=None, no=None):
        if no is None:
            no = self.tree.focus()
        if not no:
            return
        valores = self.tree.item(no, "values")
        if not valores:
            return
        caminho, tipo = valores[0], valores[1] if len(valores) > 1 else ""
        if tipo != "dir":
            return
        filhos = self.tree.get_children(no)
        if len(filhos) == 1 and self.tree.item(filhos[0], "values") and self.tree.item(filhos[0], "values")[1] == "placeholder":
            self.tree.delete(filhos[0])
            self._tree_adicionar_filhos(no, Path(caminho))

    def _alternar_no(self, event=None):
        no = self.tree.focus()
        if not no:
            return
        valores = self.tree.item(no, "values")
        if not valores:
            return
        caminho, tipo = valores[0], valores[1] if len(valores) > 1 else ""
        if tipo == "dir":
            aberto = bool(self.tree.item(no, "open"))
            if aberto:
                self.tree.item(no, open=False)
            else:
                self.tree.item(no, open=True)
                self._expandir_no(no=no)

    def _abrir_menu_contexto(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.tree.selection_set(item)
        self.tree.focus(item)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Abrir", command=lambda i=item: self._abrir_item(i))
        menu.add_command(label="Copiar", command=lambda i=item: self._copiar_item(i))
        menu.add_command(label="Remover", command=lambda i=item: self._remover_item(i))
        menu.add_separator()
        menu.add_command(label="Abrir no Explorer", command=lambda i=item: self._abrir_no_explorer(i))
        menu.tk_popup(event.x_root, event.y_root)

    def _item_caminho_tipo(self, item):
        valores = self.tree.item(item, "values")
        if not valores:
            return None, None
        caminho = Path(valores[0])
        tipo = valores[1] if len(valores) > 1 else ""
        return caminho, tipo

    def _abrir_item(self, item):
        caminho, tipo = self._item_caminho_tipo(item)
        if caminho is None:
            return
        if tipo == "dir":
            aberto = bool(self.tree.item(item, "open"))
            self.tree.item(item, open=not aberto)
            if not aberto:
                self._expandir_no(no=item)
        elif tipo == "file":
            self.on_file_selected(caminho)

    def _copiar_item(self, item):
        caminho, _ = self._item_caminho_tipo(item)
        if caminho is None:
            return
        self.clipboard_clear()
        self.clipboard_append(str(caminho))

    def _remover_item(self, item):
        caminho, tipo = self._item_caminho_tipo(item)
        if caminho is None:
            return
        if not messagebox.askyesno("Confirmar", f"Remover {'pasta' if tipo == 'dir' else 'arquivo'}?\n{caminho}"):
            return
        try:
            if caminho.is_dir():
                shutil.rmtree(caminho)
            else:
                caminho.unlink()
            self.recarregar()
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _abrir_no_explorer(self, item):
        caminho, _ = self._item_caminho_tipo(item)
        if caminho is None:
            return
        alvo = str(caminho if caminho.is_dir() else caminho.parent)
        os.startfile(alvo)

    def _iniciar_drag(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            self._drag_item = None
            return
        self._drag_item = item

    def _arrastar_item(self, event):
        if not self._drag_item:
            return
        if self._drag_overlay is None:
            self._drag_overlay = tk.Label(self, text=self.tree.item(self._drag_item, "text"), bd=1, relief="solid", bg="#fef7cc")
            self._drag_overlay.place(x=event.x_root - self.winfo_rootx() + 12, y=event.y_root - self.winfo_rooty() + 12)
        else:
            self._drag_overlay.place(x=event.x_root - self.winfo_rootx() + 12, y=event.y_root - self.winfo_rooty() + 12)

    def _soltar_item(self, event):
        if not self._drag_item:
            return

        alvo = self.tree.identify_row(event.y)
        origem = self._drag_item
        self._drag_item = None

        if self._drag_overlay is not None:
            self._drag_overlay.destroy()
            self._drag_overlay = None

        if not alvo or alvo == origem:
            return

        destino_caminho, destino_tipo = self._item_caminho_tipo(alvo)
        origem_caminho, origem_tipo = self._item_caminho_tipo(origem)
        if destino_caminho is None or origem_caminho is None:
            return
        if destino_tipo != "dir":
            return
        if destino_caminho in origem_caminho.parents or destino_caminho == origem_caminho:
            return

        try:
            novo_destino = destino_caminho / origem_caminho.name
            shutil.move(str(origem_caminho), str(novo_destino))
            self.recarregar()
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def caminhos_selecionados(self):
        caminhos = []
        vistos = set()
        for no in self.tree.selection():
            valores = self.tree.item(no, "values")
            if not valores:
                continue
            caminho = Path(valores[0])
            tipo = valores[1] if len(valores) > 1 else ""
            if tipo == "dir":
                resolvido = str(caminho.resolve())
                if resolvido not in vistos:
                    vistos.add(resolvido)
                    caminhos.append(caminho)
            elif tipo == "file":
                resolvido = str(caminho.resolve())
                if resolvido not in vistos:
                    vistos.add(resolvido)
                    caminhos.append(caminho)
        return caminhos

    def caminho_selecionado(self) -> Optional[Path]:
        selecionados = self.caminhos_selecionados()
        return selecionados[0] if selecionados else None

    def selecionar_caminho(self, caminho: str):
        alvo = Path(caminho).resolve()
        for item in self.tree.get_children(""):
            encontrado = self._buscar_item(item, alvo)
            if encontrado:
                self.tree.selection_set(encontrado)
                self.tree.see(encontrado)
                self.tree.focus(encontrado)
                return

    def _buscar_item(self, item, alvo: Path):
        valores = self.tree.item(item, "values")
        if valores and Path(valores[0]).resolve() == alvo:
            return item
        self._expandir_no(no=item)
        for filho in self.tree.get_children(item):
            achado = self._buscar_item(filho, alvo)
            if achado:
                return achado
        return None


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
        self._ui_zoom = 1.0
        self._base_scaling = float(self.root.tk.call("tk", "scaling"))
        self._fontes_base = self._registrar_fontes_base()
        self.ZOOM_IN_SEQUENCES = (
            "<Control-plus>",
            "<Control-equal>",
            "<Control-KeyPress-equal>",
            "<Control-KeyPress-plus>",
            "<Control-KP_Add>",
            "<Control-Shift-equal>",
            "<Control-KeyPress-asterisk>",
        )
        self.ZOOM_OUT_SEQUENCES = (
            "<Control-minus>",
            "<Control-underscore>",
            "<Control-KeyPress-underscore>",
            "<Control-KeyPress-minus>",
            "<Control-KP_Subtract>",
        )

        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True)

        self.tab_imagens = tk.Frame(self.tabs)
        self.tab_anuncio = tk.Frame(self.tabs)
        self.tab_mascara = tk.Frame(self.tabs)

        self.tabs.add(self.tab_imagens, text="Imagens")
        self.tabs.add(self.tab_mascara, text="Máscara")
        self.tabs.add(self.tab_anuncio, text="Anúncio")

        self.tabs.bind(
            "<<NotebookTabChanged>>",
            self.on_tab_changed
        )

        self._anuncio_app = None
        self._mascara_app = None

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

        conteudo = ttk.PanedWindow(self.tab_imagens, orient="horizontal")
        conteudo.pack(fill="both", expand=True)

        self.frame_antes = tk.LabelFrame(conteudo, text="Imagens", width=540)
        self.frame_mascaras = tk.LabelFrame(conteudo, text="Máscaras", width=300)
        self.frame_depois = tk.LabelFrame(conteudo, text="Destino", width=300)

        conteudo.add(self.frame_antes, weight=3)
        conteudo.add(self.frame_mascaras, weight=1)
        conteudo.add(self.frame_depois, weight=1)

        self.frame_antes.configure(padx=5, pady=5)
        self.frame_mascaras.configure(padx=5, pady=5)
        self.frame_depois.configure(padx=5, pady=5)

        self.browser_imagens = NavegadorArquivos(
            self.frame_antes,
            self.imagens_path,
            titulo="Imagens",
            multisselecao=True,
        )
        self.browser_imagens.pack(fill="both", expand=True)
        self.grid_imagens_antes = self.browser_imagens

        botoes_antes = tk.Frame(self.frame_antes)
        botoes_antes.pack(side="bottom", fill="x", pady=5)
        tk.Button(
            botoes_antes,
            text="Escolher Imagens",
            command=lambda: self.acao_botao("Escolher Imagens", self.browser_imagens),
        ).pack(side="left", padx=5)
        tk.Button(
            botoes_antes,
            text="Limpar Imagens",
            command=lambda: self.acao_botao("Limpar Imagens", self.browser_imagens),
        ).pack(side="left", padx=5)
        tk.Button(
            botoes_antes,
            text="Atualizar",
            command=self.carregar_imagens,
        ).pack(side="left", padx=5)

        self.browser_mascaras = NavegadorArquivos(
            self.frame_mascaras,
            self.mascaras_path,
            titulo="Máscaras",
            multisselecao=False,
        )
        self.browser_mascaras.pack(fill="both", expand=True)
        self.grid_mascaras = self.browser_mascaras
        self.lista_mascaras = self.browser_mascaras

        self.browser_mascaras.tree.bind("<<TreeviewSelect>>", self._atualizar_mascara_selecionada)

        botoes_mascaras = tk.Frame(self.frame_mascaras)
        botoes_mascaras.pack(side="bottom", fill="x", pady=5)
        tk.Button(
            botoes_mascaras,
            text="Escolher Imagens",
            command=lambda: self.acao_botao("Escolher Imagens", self.browser_mascaras),
        ).pack(side="left", padx=5)
        tk.Button(
            botoes_mascaras,
            text="Atualizar Máscaras",
            command=self.carregar_mascaras,
        ).pack(side="left", padx=5)

        self.browser_destino = NavegadorArquivos(
            self.frame_depois,
            self.destino_path,
            titulo="Destino",
            multisselecao=True,
        )
        self.browser_destino.pack(fill="both", expand=True)
        self.grid_imagens_depois = self.browser_destino

        botoes_depois = tk.Frame(self.frame_depois)
        botoes_depois.pack(side="bottom", fill="x", pady=5)
        tk.Button(
            botoes_depois,
            text="Escolher Imagens",
            command=lambda: self.acao_botao("Escolher Imagens", self.browser_destino),
        ).pack(side="left", padx=5)
        tk.Button(
            botoes_depois,
            text="Limpar Imagens",
            command=lambda: self.acao_botao("Limpar Imagens", self.browser_destino),
        ).pack(side="left", padx=5)
        tk.Button(
            botoes_depois,
            text="Atualizar",
            command=self.carregar_destino,
        ).pack(side="left", padx=5)

        self.carregar_imagens()
        self.carregar_mascaras()
        self.carregar_destino()

    def carregar_imagens(self):
        self.browser_imagens.recarregar()

    def carregar_mascaras(self):
        self.browser_mascaras.recarregar()

    def carregar_destino(self):
        self.browser_destino.recarregar()

    def adicionar_imagem(self, frame, caminho):
        if frame in (self.browser_imagens, self.grid_imagens_antes):
            self.browser_imagens.recarregar()
        elif frame in (self.browser_destino, self.grid_imagens_depois):
            self.browser_destino.recarregar()
        elif frame in (self.browser_mascaras, self.grid_mascaras, self.lista_mascaras):
            self.browser_mascaras.recarregar()
            self._atualizar_mascara_selecionada()

    def _registrar_fontes_base(self):
        fontes = {}
        for nome in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkFixedFont",
        ):
            try:
                fontes[nome] = tkfont.nametofont(nome)
            except Exception:
                continue
        return fontes

    def _atualizar_estilo_ui(self):
        for fonte in self._fontes_base.values():
            dados = fonte.actual()
            tamanho_base = abs(int(dados.get("size", 10))) or 10
            fonte.configure(size=max(7, int(round(tamanho_base * self._ui_zoom))))

        try:
            estilo = ttk.Style(self.root)
            rowheight = max(18, int(round(22 * self._ui_zoom)))
            estilo.configure("Treeview", rowheight=rowheight)
            estilo.configure("Browser.Treeview", rowheight=max(18, int(round((72 + 16) * self._ui_zoom))))
        except Exception:
            pass

        for browser in (
            getattr(self, "browser_imagens", None),
            getattr(self, "browser_mascaras", None),
            getattr(self, "browser_destino", None),
        ):
            if browser is not None:
                browser.aplicar_zoom_interface(self._ui_zoom)

    def _aplicar_zoom_ui(self, fator: float):
        self._ui_zoom = max(0.75, min(1.75, round(fator, 3)))
        self.root.tk.call("tk", "scaling", self._base_scaling * self._ui_zoom)
        self._atualizar_estilo_ui()
        self.root.title(f"Removedor de Logos - {int(self._ui_zoom * 100)}%")
        return "break"

    def _aumentar_zoom_ui(self, event=None):
        if self.tabs.index(self.tabs.select()) == 1 and self._mascara_app is not None:
            return "break"
        return self._aplicar_zoom_ui(self._ui_zoom * 1.1)

    def diminuir_zoom_ui(self, event=None):
        if self.tabs.index(self.tabs.select()) == 1 and self._mascara_app is not None:
            return "break"
        return self._aplicar_zoom_ui(self._ui_zoom / 1.1)

    def _ativar_zoom_global(self):
        if self._mascara_app is not None:
            self._mascara_app.desativar_atalhos()
        for seq in self.ZOOM_IN_SEQUENCES:
            self.root.bind_all(seq, self._aumentar_zoom_ui, add="+")
        for seq in self.ZOOM_OUT_SEQUENCES:
            self.root.bind_all(seq, self.diminuir_zoom_ui, add="+")

    def _desativar_zoom_global(self):
        for seq in self.ZOOM_IN_SEQUENCES:
            self.root.unbind_all(seq)
        for seq in self.ZOOM_OUT_SEQUENCES:
            self.root.unbind_all(seq)

    def selecionar_mascara(self, event):
        self._atualizar_mascara_selecionada(event)

    def _atualizar_mascara_selecionada(self, event=None):
        selecionado = self.browser_mascaras.caminho_selecionado()
        self.caminho_mascara_selecionada = str(selecionado) if selecionado and selecionado.is_file() else ""

    def _carregar_tela_anuncio(self):
        if self._anuncio_app is None:
            self._anuncio_app = AnuncioApp(
                self.root,
                container=self.tab_anuncio,
            )

    def _carregar_tela_mascara(self):
        if self._mascara_app is None:
            self._mascara_app = LogoPainterApp(
                self.root,
                folder=str(Path(".").resolve()),
                iopaint_url="http://localhost:8080",
                container=self.tab_mascara,
            )
        self._mascara_app.ativar_atalhos()

    def on_tab_changed(self, event):

        indice = self.tabs.index(
            self.tabs.select()
        )

        if indice == 2:
            self._desativar_zoom_global()
            self._carregar_tela_anuncio()
        elif indice == 1:
            self._desativar_zoom_global()
            self._carregar_tela_mascara()
        else:
            if self._mascara_app is not None:
                self._mascara_app.desativar_atalhos()
            self._ativar_zoom_global()

    def acao_botao(self, acao, container=None):

        match acao:

            case "Atualizar Máscaras":
                self.carregar_mascaras()

            case "Abrir Diretório":

                os.startfile(self.home)

            case "Escolher Imagens":

                imagens = selecionar_arquivos()

                if not imagens:
                    return

                if container == self.browser_imagens:
                    destino = self.imagens_path

                elif container == self.browser_destino:
                    destino = self.destino_path

                elif container == self.browser_mascaras:
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

                        if container == self.browser_mascaras:
                            self.carregar_mascaras()
                        elif container == self.browser_destino:
                            self.carregar_destino()
                        else:
                            self.carregar_imagens()

                    except Exception as e:

                        messagebox.showerror(
                            "Erro",
                            f"Erro ao copiar imagem: {e}"
                        )

            case "Limpar Imagens":

                try:

                    destino = ""

                    if not messagebox.askyesno(
                        "Confirmação",
                        "Deseja realmente limpar as imagens?"
                    ):
                        return

                    if container == self.browser_imagens:
                        destino = self.imagens_path

                    elif container == self.browser_destino:
                        destino = self.destino_path

                    else:
                        return

                    for raiz, _, arquivos in os.walk(destino):
                        for arquivo in arquivos:
                            caminho = os.path.join(raiz, arquivo)
                            if os.path.isfile(caminho):
                                os.remove(caminho)

                    if container == self.browser_imagens:
                        self.carregar_imagens()
                    else:
                        self.carregar_destino()

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

                    self._atualizar_mascara_selecionada()

                    if not self.caminho_mascara_selecionada:

                        messagebox.showwarning(
                            "Aviso",
                            "Selecione uma máscara"
                        )

                        return

                    alvos = self.browser_imagens.caminhos_selecionados()
                    if not alvos:
                        alvos = [self.imagens_path]

                    threading.Thread(
                        target=self.pintagem,
                        args=(self.caminho_mascara_selecionada, alvos),
                        daemon=True
                    ).start()

                except Exception as e:

                    messagebox.showerror(
                        "Erro",
                        str(e)
                    )

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

                nome_pasta = getattr(self, "nome_pasta", None)
                nome_pasta = nome_pasta.get().strip() if nome_pasta else ""

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

                            img_data = requests.get(
                                img_url, headers=headers).content

                            img_path = os.path.join(
                                imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                                                urls.append(
                                                    normalizar(item[k]))

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

                            imagens.extend(re.findall(
                                padrao, html, flags=re.IGNORECASE))

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
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(
                                img_url, headers=headers, timeout=10).content
                            img_path = os.path.join(
                                imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(
                                img_url, headers=headers, timeout=10).content
                            img_path = os.path.join(
                                imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

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
                                lambda p=save_path: self.adicionar_imagem_na_ui(
                                    p)
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

                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

                    print(f"Encontradas {len(imagens)} imagens")

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")

                            img_data = requests.get(
                                img_url, headers=headers).content

                            img_path = os.path.join(
                                imagens_path, f"img_{i}.jpg")

                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))
                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")
                            img_data = requests.get(
                                img_url, headers=headers).content
                            img_path = os.path.join(
                                imagens_path, f"img_{i}.jpg")
                            with open(img_path, "wb") as f:
                                f.write(img_data)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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
                            resp = requests.get(
                                img_url, headers=headers, timeout=10)

                            if resp.status_code != 200:
                                print(f"Erro {resp.status_code}: {img_url}")
                                continue

                            nome_arquivo = f"img_{i}.jpg"

                            img_path = os.path.join(imagens_path, nome_arquivo)

                            with open(img_path, "wb") as f:
                                f.write(resp.content)

                            self.root.after(
                                0,
                                lambda p=img_path: self.adicionar_imagem_na_ui(
                                    p)
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

                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            resp = requests.get(
                                img_url, headers=headers, timeout=10)

                            if resp.status_code != 200:
                                continue

                            nome = f"img_{i}.jpg"
                            caminho = f"{imagens_path}/{nome}"

                            with open(caminho, "wb") as f:
                                f.write(resp.content)

                            self.root.after(
                                0,
                                lambda p=caminho: self.adicionar_imagem_na_ui(
                                    p)
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
                                re.sub(r"/outer/\d+/", "/outer/1920/",
                                       img_url, count=1)
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
                        imagens_data = produto.get(
                            "images", {}).get("data", [])

                        imagens = [
                            _foxter_url_alta_resolucao(item["etag"])
                            for item in imagens_data
                            if item.get("etag")
                        ]
                    except Exception:
                        pattern = r"https://images\.foxter\.com\.br/[^\s\"']+\.jpg"
                        imagens_brutas = list(
                            dict.fromkeys(re.findall(pattern, html)))
                        imagens = [
                            _foxter_url_alta_resolucao(img_url)
                            for img_url in imagens_brutas
                        ]

                    print(f"Encontradas {len(imagens)} imagens")

                    headers_img = {
                        "User-Agent": headers["User-Agent"],
                        "Referer": "https://www.foxterciaimobiliaria.com.br/"
                    }

                    self.root.after(
                        0, lambda: self.resetar_progresso(len(imagens)))

                    for i, img_url in enumerate(imagens):
                        try:
                            print(f"Baixando: {img_url}")

                            # if worker.is_cancelled:
                            #     return

                            resp = requests.get(
                                img_url, headers=headers_img, timeout=10)

                            if resp.status_code == 200:
                                img_path = os.path.join(
                                    imagens_path, f"img_{i}.jpg")

                                with open(img_path, "wb") as f:
                                    f.write(resp.content)

                                self.root.after(
                                    0,
                                    lambda p=img_path: self.adicionar_imagem_na_ui(
                                        p)
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
                    lambda err=str(e): print(f"Erro geral: {err}")
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

            self.carregar_imagens()

            if os.path.exists(caminho_imagem):
                self.browser_imagens.selecionar_caminho(caminho_imagem)

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

    def _coletar_imagens_para_processar(self, alvos=None):
        extensoes = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif")
        if not alvos:
            alvos = [self.imagens_path]

        arquivos = []
        vistos = set()

        for alvo in alvos:
            caminho = Path(alvo)
            if caminho.is_file() and caminho.suffix.lower() in extensoes:
                resolvido = str(caminho.resolve())
                if resolvido not in vistos:
                    vistos.add(resolvido)
                    arquivos.append(resolvido)
                continue

            if caminho.is_dir():
                for raiz, _, nomes in os.walk(caminho):
                    for nome in nomes:
                        if nome.lower().endswith(extensoes):
                            caminho_arquivo = Path(raiz) / nome
                            resolvido = str(caminho_arquivo.resolve())
                            if resolvido not in vistos:
                                vistos.add(resolvido)
                                arquivos.append(resolvido)

        return arquivos

    def _destino_para_imagem(self, caminho_imagem: str):
        origem = Path(caminho_imagem).resolve()
        try:
            rel_dir = origem.parent.relative_to(Path(self.imagens_path).resolve())
            destino = Path(self.destino_path).resolve()
            if str(rel_dir) != ".":
                destino = destino / rel_dir
            destino.mkdir(parents=True, exist_ok=True)
            return destino
        except Exception:
            destino = Path(self.destino_path).resolve()
            destino.mkdir(parents=True, exist_ok=True)
            return destino

    def pintagem(self, mascara, alvos=None):

        def tarefa(mascara, alvos):

            etapas_total = 5

            try:

                imagens_para_processar = self._coletar_imagens_para_processar(alvos)

                if not imagens_para_processar:
                    self.root.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Aviso",
                            "Nenhuma imagem encontrada na seleção atual."
                        )
                    )
                    return

                self.root.after(
                    0, lambda: self.resetar_progresso(etapas_total))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Info",
                    "Iniciando remoção de logo..."
                ))

                destino_path = os.path.join(self.home, "Destino")
                for caminho_imagem in imagens_para_processar:

                    try:

                        destino_imagem = str(self._destino_para_imagem(caminho_imagem))
                        nome_saida = os.path.basename(caminho_imagem)
                        saida_final = os.path.join(destino_imagem, nome_saida)

                        if os.path.exists(saida_final):
                            print(f"Pulando {caminho_imagem} porque já foi processada.")
                            continue

                        resolucao = Image.open(caminho_imagem).size
                        mascaraObj = Image.open(mascara).resize(resolucao)
                        mascara_temp_path = os.path.join(self.home, "mascara_temp.png")
                        mascaraObj.save(mascara_temp_path)

                        cmd = [
                            "iopaint", "run",
                            "--image", caminho_imagem,
                            "--mask", mascara_temp_path,
                            "--output", destino_imagem,
                        ]

                        self.root.after(0, lambda c=cmd: print("Executando:", " ".join(c)))

                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )

                        stdout, stderr = process.communicate()

                        if process.returncode == 0:
                            self.root.after(0, self.carregar_destino)
                        else:
                            print(stderr or stdout)

                        if os.path.exists(mascara_temp_path):
                            os.remove(mascara_temp_path)

                    except Exception as e:
                        print(f"Erro ao processar {caminho_imagem}: {e}")
                        continue

            except Exception as e:

                self.root.after(
                    0,
                    lambda erro=str(e): messagebox.showerror(
                        "Erro",
                        f"Erro na pintagem: {erro}"
                    )
                )

        threading.Thread(target=tarefa, args=(mascara, alvos), daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":

    root = tk.Tk()
    root.geometry("1000x700")

    app = App(root)

    root.mainloop()
