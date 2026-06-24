import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

from model.modelo import Modelo


class AnuncioApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Gerador de Anúncios")

        self.imagens = []

        self.modelo_atual = Modelo()
        self.modelo_atual.modelo = "llava:13b"

        self.verificar_modelos_imagem()

        self.criar_interface()

    def verificar_modelos_imagem(self):
        if not self.modelo_atual.listar_nome_modelos():
            messagebox.showwarning(
                "Aviso",
                "Não há nenhum modelo do Ollama instalado"
            )
            return

        for modelo in self.modelo_atual.listar_nome_modelos():
            self.modelo_atual.modelo = modelo

            if self.modelo_atual.suporta_imagem:
                return

        self.modelo_atual.modelo = None
        messagebox.showwarning(
            "Aviso",
            "Nenhum modelo suporta imagem"
        )

    def criar_interface(self):

        tk.Button(
            self.root,
            text="Selecionar Imagem",
            command=self.selecionar_imagens
        ).pack(pady=10)

        self.frame_imagens = tk.Frame(self.root)
        self.frame_imagens.pack(fill="x", padx=10)

        tk.Button(
            self.root,
            text="Gerar Anúncio",
            command=self.gerar_anuncio
        ).pack(pady=10)

        frame_titulo = tk.Frame(self.root)
        frame_titulo.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_titulo, text="Título:").pack(side="left")

        self.entry_titulo = tk.Entry(frame_titulo)
        self.entry_titulo.pack(side="left", fill="x", expand=True)

        frame_descricao = tk.Frame(self.root)
        frame_descricao.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_descricao, text="Descrição:").pack(side="left")

        self.entry_descricao = tk.Entry(frame_descricao)
        self.entry_descricao.pack(side="left", fill="x", expand=True)

        self.text_area = tk.Text(self.root, height=15)
        self.text_area.pack(fill="both", expand=True, padx=10, pady=10)

        self.thumbnails = []

    def selecionar_imagens(self):

        arquivos = filedialog.askopenfilenames(
            title="Selecionar imagens",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp")
            ]
        )

        if not arquivos:
            return

        self.imagens = list(arquivos)

        for widget in self.frame_imagens.winfo_children():
            widget.destroy()

        self.thumbnails.clear()

        for caminho in self.imagens:
            try:
                img = Image.open(caminho)
                img.thumbnail((150, 150))

                foto = ImageTk.PhotoImage(img)
                self.thumbnails.append(foto)

                lbl = tk.Label(self.frame_imagens, image=foto)
                lbl.pack(side="left", padx=5)

            except Exception as e:
                print(e)

    def gerar_anuncio(self):

        if not self.imagens:
            messagebox.showwarning(
                "Aviso",
                "Selecione ao menos uma imagem."
            )
            return

        mensagem = """
Gerar um TEXTO anúncio com titulo e descricao com base nas imagens.

Ser profissional, não usar emojis e não falar tanto sobre valores.

Respeite esse formato:

Titulo: "titulo do anuncio"

Descrição: "descrição do anuncio"

ATENÇÃO:
A imagem enviada é referente a um imóvel,
então o anúncio deve ser sobre um imóvel,
e deve ser um anúncio profissional,
focado em vender ou alugar o imóvel.
"""

        try:

            resposta = self.modelo_atual.enviar_mensagem(
                mensagem=mensagem,
                imagens=self.imagens
            )

            messagebox.showinfo("Resposta", "Anúncio gerado com sucesso!")

            try:
                titulo = resposta.split("titulo:")[1] \
                    .split("descrição:")[0] \
                    .strip()

                descricao = resposta.split("descrição:")[1].strip()

                self.entry_titulo.delete(0, tk.END)
                self.entry_titulo.insert(0, titulo)

                self.entry_descricao.delete(0, tk.END)
                self.entry_descricao.insert(0, descricao)

            except Exception:

                self.text_area.delete("1.0", tk.END)
                self.text_area.insert(tk.END, resposta)

                messagebox.showwarning(
                    "Aviso",
                    "Não foi possível extrair título e descrição."
                )

        except Exception as e:
            messagebox.showerror(
                "Erro",
                str(e)
            )


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x700")

    app = AnuncioApp(root)

    root.mainloop()