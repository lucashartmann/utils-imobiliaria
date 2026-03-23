import tkinter as tk
from tkinter import filedialog


def selecionar_arquivos():
    try:
        root = tk.Tk()
        root.withdraw()

        caminhos = filedialog.askopenfilenames(
            title="Selecione",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg")]
        )

        caminhos = list(caminhos)

        root.destroy()
        return caminhos
    except Exception as e:
        print(e)
        pass
