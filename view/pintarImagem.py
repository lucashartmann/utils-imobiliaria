import argparse
import io
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from typing import Optional

import requests
from PIL import Image as PILImage, ImageDraw, ImageTk

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}


class SaveResultDialog(tk.Toplevel):
    def __init__(self, parent, result_image: PILImage.Image, original_path: Path):
        super().__init__(parent)
        self.result_image = result_image
        self.original_path = original_path
        self.choice = None

        self.title("IOPaint concluído")
        self.resizable(False, False)
        self.grab_set()

        pad = dict(padx=12, pady=6)

        tk.Label(self, text="IOPaint concluído!", font=("", 12, "bold"),
                 fg="#2d8a4e").pack(**pad)
        tk.Label(self,
                 text=f"Imagem processada com sucesso.\nArquivo original: {original_path.name}",
                 justify="left").pack(**pad)

        ttk.Button(self, text="Substituir original",
                   command=self._overwrite).pack(fill="x", padx=12, pady=3)
        ttk.Button(self, text="Salvar como *_inpainted.png",
                   command=self._saveas).pack(fill="x", padx=12, pady=3)
        ttk.Button(self, text="Voltar (descartar resultado)",
                   command=self._discard).pack(fill="x", padx=12, pady=(3, 12))

        self.protocol("WM_DELETE_WINDOW", self._discard)
        self.wait_window()

    def _overwrite(self):
        self.result_image.save(self.original_path)
        self.choice = ("overwrite", self.original_path)
        self.destroy()

    def _saveas(self):
        out = self.original_path.parent / \
            f"{self.original_path.stem}_inpainted.png"
        self.result_image.save(out)
        self.choice = ("saveas", out)
        self.destroy()

    def _discard(self):
        self.choice = ("discard", None)
        self.destroy()


class CriarMascaraDialog(tk.Toplevel):
    def __init__(self, parent, callback, width=800, height=600):
        super().__init__(parent)
        self.title("Criar Máscara")
        self.geometry("1200x800")
        self.resizable(True, True)
        self.callback = callback
        self._mask_w = width
        self._mask_h = height
        self.brush_size = 20
        self.erase_mode = False
        self.zoom = 1.0
        self._mouse_down = False
        self._undo_stack: list[bytes] = []
        self.mask = PILImage.new("L", (self._mask_w, self._mask_h), 0)
        self._draw = ImageDraw.Draw(self.mask)
        self._build_ui()
        self._refresh()
        self.bind("<Control-z>", lambda e: self._undo())
        self.bind("<c>", lambda e: self._clear())

    def _build_ui(self):
        top = tk.Frame(self, bg="#2b2b2b")
        top.pack(fill="x")
        tk.Label(top, text="Tamanho:", bg="#2b2b2b",
                 fg="white").pack(side="left", padx=(8, 2))
        self._var_w = tk.StringVar(value=str(self._mask_w))
        self._var_h = tk.StringVar(value=str(self._mask_h))
        tk.Entry(top, textvariable=self._var_w,
                 width=6).pack(side="left", padx=2)
        tk.Label(top, text="×", bg="#2b2b2b", fg="white").pack(side="left")
        tk.Entry(top, textvariable=self._var_h,
                 width=6).pack(side="left", padx=2)
        ttk.Button(top, text="Aplicar tamanho",
                   command=self._apply_size).pack(side="left", padx=6)
        tk.Label(top, text="|", bg="#2b2b2b",
                 fg="#555").pack(side="left", padx=4)
        ttk.Button(top, text="Confirmar máscara",
                   command=self._confirm).pack(side="left", padx=4)
        ttk.Button(top, text="Cancelar", command=self.destroy).pack(
            side="left", padx=4)
        main = tk.Frame(self)
        main.pack(fill="both", expand=True)
        side = tk.Frame(main, bg="#1e1e1e", width=160)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self._build_side(side)
        frame_canvas = tk.Frame(main)
        frame_canvas.pack(side="left", fill="both", expand=True)
        self._hbar = tk.Scrollbar(frame_canvas, orient="horizontal")
        self._hbar.pack(side="bottom", fill="x")
        self._vbar = tk.Scrollbar(frame_canvas, orient="vertical")
        self._vbar.pack(side="right", fill="y")
        self.canvas = tk.Canvas(
            frame_canvas,
            bg="black",
            cursor="crosshair",
            xscrollcommand=self._hbar.set,
            yscrollcommand=self._vbar.set,
        )
        self.canvas.pack(fill="both", expand=True)
        self._hbar.config(command=self.canvas.xview)
        self._vbar.config(command=self.canvas.yview)

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self._on_mouse_down_erase)
        self.canvas.bind("<B3-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-3>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", self._on_scroll)
        self.canvas.bind("<Button-5>", self._on_scroll)
        self._status_var = tk.StringVar(
            value="Pinte a máscara • Esq=branco  Dir=apagar  Scroll=zoom")
        tk.Label(self, textvariable=self._status_var, anchor="w",
                 bg="#111", fg="#aaa").pack(fill="x")

    def _build_side(self, parent):
        def lbl(text, **kw):
            tk.Label(parent, text=text, bg="#1e1e1e", fg="#cccccc",
                     anchor="w").pack(fill="x", padx=8, pady=(6, 0))

        def btn(text, cmd, **kw):
            ttk.Button(parent, text=text, command=cmd, **kw).pack(
                fill="x", padx=8, pady=2)

        lbl("Máscara", font=("", 10, "bold"))
        lbl("──────────────")

        lbl("Modo")
        btn("Pintar", self._set_paint)
        btn("Apagar", self._set_erase)

        lbl("Pincel")
        self._brush_lbl = tk.StringVar(value=f"{self.brush_size}px")
        tk.Label(parent, textvariable=self._brush_lbl, bg="#1e1e1e",
                 fg="#56a0d3").pack(fill="x", padx=8)
        btn("−  Menor", self._brush_smaller)
        btn("+  Maior", self._brush_bigger)
        lbl("Zoom")
        btn("Zoom In", self._zoom_in)
        btn("Zoom Out", self._zoom_out)
        btn("1:1 Reset", self._zoom_reset)
        lbl("──────────────")
        btn("↩ Desfazer (Ctrl+Z)", self._undo)
        btn("🗑  Limpar (C)", self._clear)

    def _apply_size(self):
        try:
            w = max(1, int(self._var_w.get()))
            h = max(1, int(self._var_h.get()))
        except ValueError:
            messagebox.showerror(
                "Erro", "Largura e altura devem ser números inteiros.", parent=self)
            return
        self._mask_w, self._mask_h = w, h
        self._undo_stack.clear()
        self.mask = PILImage.new("L", (w, h), 0)
        self._draw = ImageDraw.Draw(self.mask)
        self.zoom = 1.0
        self._refresh()

    def _canvas_to_mask(self, cx, cy):
        sx = self.canvas.canvasx(cx)
        sy = self.canvas.canvasy(cy)
        px = int(sx / self.zoom)
        py = int(sy / self.zoom)
        px = max(0, min(self._mask_w - 1, px))
        py = max(0, min(self._mask_h - 1, py))
        return px, py

    def _paint_at(self, cx, cy):
        px, py = self._canvas_to_mask(cx, cy)
        r = self.brush_size
        color = 0 if self.erase_mode else 255
        self._draw.ellipse([px - r, py - r, px + r, py + r], fill=color)
        self._refresh()

    def _on_mouse_down(self, event):
        self._mouse_down = True
        self.erase_mode = False
        self._push_undo()
        self._paint_at(event.x, event.y)

    def _on_mouse_down_erase(self, event):
        self._mouse_down = True
        self.erase_mode = True
        self._push_undo()
        self._paint_at(event.x, event.y)

    def _on_mouse_move(self, event):
        if self._mouse_down:
            self._paint_at(event.x, event.y)

    def _on_mouse_up(self, event):
        self._mouse_down = False

    def _on_scroll(self, event):
        if event.num == 4 or event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    def _zoom_in(self):
        self.zoom = min(8.0, round(self.zoom * 1.25, 3))
        self._refresh()

    def _zoom_out(self):
        self.zoom = max(0.1, round(self.zoom / 1.25, 3))
        self._refresh()

    def _zoom_reset(self):
        self.zoom = 1.0
        self._refresh()

    def _refresh(self):
        nw = max(1, int(self._mask_w * self.zoom))
        nh = max(1, int(self._mask_h * self.zoom))
        display = self.mask.resize((nw, nh), PILImage.NEAREST).convert("RGB")
        self._tk_img = ImageTk.PhotoImage(display)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.canvas.configure(scrollregion=(0, 0, nw, nh))
        self._brush_lbl.set(f"{self.brush_size}px  zoom:{self.zoom:.1f}×")

    def _push_undo(self):
        self._undo_stack.append(self.mask.tobytes())
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            self._status_var.set("Nada para desfazer")
            return
        data = self._undo_stack.pop()
        self.mask = PILImage.frombytes("L", (self._mask_w, self._mask_h), data)
        self._draw = ImageDraw.Draw(self.mask)
        self._refresh()
        self._status_var.set("Desfeito")

    def _clear(self):
        self._push_undo()
        self.mask = PILImage.new("L", (self._mask_w, self._mask_h), 0)
        self._draw = ImageDraw.Draw(self.mask)
        self._refresh()
        self._status_var.set("Máscara limpa")

    def _set_paint(self):
        self.erase_mode = False
        self._status_var.set("Modo: Pintar")

    def _set_erase(self):
        self.erase_mode = True
        self._status_var.set("Modo: Apagar")

    def _brush_smaller(self):
        self.brush_size = max(2, self.brush_size - 5)
        self._brush_lbl.set(f"{self.brush_size}px  zoom:{self.zoom:.1f}×")

    def _brush_bigger(self):
        self.brush_size = min(200, self.brush_size + 10)
        self._brush_lbl.set(f"{self.brush_size}px  zoom:{self.zoom:.1f}×")

    def _confirm(self):
        self.callback(self.mask.copy())
        self.destroy()


class MaskCanvas(tk.Frame):
    def __init__(self, parent, on_status=None, on_brush_info=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_status = on_status or (lambda msg: None)
        self.on_brush_info = on_brush_info or (lambda msg: None)
        self.orig: Optional[PILImage.Image] = None
        self.mask: Optional[PILImage.Image] = None
        self._draw: Optional[ImageDraw.ImageDraw] = None
        self._undo_stack: list[bytes] = []
        self._mouse_down = False
        self.brush_size = 20
        self.erase_mode = False
        self.zoom = 1.0
        self._tk_img = None
        self._hbar = tk.Scrollbar(self, orient="horizontal")
        self._hbar.pack(side="bottom", fill="x")
        self._vbar = tk.Scrollbar(self, orient="vertical")
        self._vbar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(
            self,
            bg="#1e1e1e",
            cursor="crosshair",
            xscrollcommand=self._hbar.set,
            yscrollcommand=self._vbar.set,
        )
        self.canvas.pack(fill="both", expand=True)
        self._hbar.config(command=self.canvas.xview)
        self._vbar.config(command=self.canvas.yview)

        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<ButtonPress-3>", self._on_mouse_down_erase)
        self.canvas.bind("<B3-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-3>", self._on_mouse_up)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>", self._on_scroll)
        self.canvas.bind("<Button-5>", self._on_scroll)

    def load_image(self, path: Path):
        self.orig = PILImage.open(path).convert("RGBA")
        self.mask = PILImage.new("L", self.orig.size, 0)
        self._draw = ImageDraw.Draw(self.mask)
        self._undo_stack.clear()
        self.zoom = 1.0
        self._refresh_display()

    def _make_composite(self) -> PILImage.Image:
        if self.orig is None:
            return PILImage.new("RGB", (400, 300), (30, 30, 30))
        base = self.orig.copy()
        overlay = PILImage.new("RGBA", base.size, (255, 0, 0, 0))
        red = PILImage.new("RGBA", base.size, (220, 50, 50, 160))
        overlay.paste(red, mask=self.mask)
        comp = PILImage.alpha_composite(base, overlay).convert("RGB")
        if self.zoom != 1.0:
            nw = max(1, int(comp.width * self.zoom))
            nh = max(1, int(comp.height * self.zoom))
            comp = comp.resize((nw, nh), PILImage.NEAREST)
        return comp

    def _refresh_display(self):
        comp = self._make_composite()
        self._tk_img = ImageTk.PhotoImage(comp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.canvas.configure(scrollregion=(0, 0, comp.width, comp.height))
        self.on_brush_info(f"{self.brush_size}px  zoom:{self.zoom:.1f}×")

    def _canvas_to_image(self, cx, cy):
        if self.orig is None:
            return 0, 0
        sx = self.canvas.canvasx(cx)
        sy = self.canvas.canvasy(cy)
        px = int(sx / self.zoom)
        py = int(sy / self.zoom)
        px = max(0, min(self.orig.width - 1, px))
        py = max(0, min(self.orig.height - 1, py))
        return px, py

    def _paint_at(self, cx, cy):
        if self.orig is None or self._draw is None:
            return
        px, py = self._canvas_to_image(cx, cy)
        r = self.brush_size
        color = 0 if self.erase_mode else 255
        self._draw.ellipse([px - r, py - r, px + r, py + r], fill=color)
        self._refresh_display()

    def _on_mouse_down(self, event):
        if self.orig is None:
            return
        self.erase_mode = False
        self._mouse_down = True
        self.push_undo()
        self._paint_at(event.x, event.y)

    def _on_mouse_down_erase(self, event):
        if self.orig is None:
            return
        self.erase_mode = True
        self._mouse_down = True
        self.push_undo()
        self._paint_at(event.x, event.y)

    def _on_mouse_move(self, event):
        if self._mouse_down:
            self._paint_at(event.x, event.y)

    def _on_mouse_up(self, event):
        self._mouse_down = False

    def _on_scroll(self, event):
        if event.num == 4 or event.delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.zoom = min(8.0, round(self.zoom * 1.25, 3))
        self._refresh_display()

    def zoom_out(self):
        self.zoom = max(0.1, round(self.zoom / 1.25, 3))
        self._refresh_display()

    def zoom_reset(self):
        self.zoom = 1.0
        self._refresh_display()

    def push_undo(self):
        if self.mask is None:
            return
        self._undo_stack.append(self.mask.tobytes())
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def undo(self):
        if not self._undo_stack or self.mask is None:
            self.on_status("Nada para desfazer")
            return
        data = self._undo_stack.pop()
        self.mask = PILImage.frombytes("L", self.mask.size, data)
        self._draw = ImageDraw.Draw(self.mask)
        self._refresh_display()
        self.on_status("Desfeito")

    def clear_mask(self):
        if self.orig is None:
            return
        self.push_undo()
        self.mask = PILImage.new("L", self.orig.size, 0)
        self._draw = ImageDraw.Draw(self.mask)
        self._refresh_display()
        self.on_status("Máscara limpa")

    def get_mask(self) -> Optional[PILImage.Image]:
        return self.mask.copy() if self.mask else None

    def get_orig(self) -> Optional[PILImage.Image]:
        return self.orig


class ImageTree(tk.Frame):
    def __init__(self, parent, folder: Path, on_file_selected=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_file_selected = on_file_selected or (lambda p: None)
        self._folder = folder

        bar = tk.Frame(self, bg="#252526")
        bar.pack(fill="x")
        tk.Label(bar, text="Arquivos", bg="#252526", fg="#569cd6",
                 font=("", 9, "bold")).pack(side="left", padx=6, pady=3)

        row = tk.Frame(self)
        row.pack(fill="x")
        self._folder_var = tk.StringVar(value=str(folder))
        tk.Entry(row, textvariable=self._folder_var).pack(
            side="left", fill="x", expand=True, padx=2, pady=2)
        ttk.Button(row, text="Ir", width=4, command=self._change_folder).pack(
            side="left", padx=2, pady=2)

        vsb = tk.Scrollbar(self, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._tree = ttk.Treeview(
            self, selectmode="browse", yscrollcommand=vsb.set, show="tree")
        self._tree.pack(fill="both", expand=True)
        vsb.config(command=self._tree.yview)

        self._tree.bind("<<TreeviewOpen>>", self._on_open)
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Return>", self._on_double_click)

        self._populate(folder)

    def _change_folder(self):
        p = Path(self._folder_var.get()).expanduser().resolve()
        if p.is_dir():
            self._folder = p
            self._populate(p)
        else:
            messagebox.showerror("Erro", f"Pasta não encontrada: {p}")

    def _populate(self, folder: Path):
        self._tree.delete(*self._tree.get_children())
        self._insert_dir("", folder)

    def _insert_dir(self, parent, folder: Path):
        for p in sorted(folder.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if p.is_dir():
                node = self._tree.insert(
                    parent, "end", text=f"{p.name}", open=False)
                self._tree.insert(node, "end", text="...")
                self._tree.item(node, values=[str(p)])
            elif p.suffix.lower() in IMAGE_EXTS:
                node = self._tree.insert(parent, "end", text=f"{p.name}")
                self._tree.item(node, values=[str(p)])

    def _on_open(self, event):
        node = self._tree.focus()
        vals = self._tree.item(node, "values")
        if not vals:
            return
        p = Path(vals[0])
        if p.is_dir():
            children = self._tree.get_children(node)
            if len(children) == 1 and self._tree.item(children[0], "text") == "...":
                self._tree.delete(children[0])
                self._insert_dir(node, p)

    def _on_double_click(self, event):
        node = self._tree.focus()
        vals = self._tree.item(node, "values")
        if not vals:
            return
        p = Path(vals[0])
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            self.on_file_selected(p)


class SidePanel(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg="#1e1e1e", **kwargs)
        self.app = app
        self._build()

    def _lbl(self, text, **kw):
        tk.Label(self, text=text, bg="#1e1e1e", fg="#cccccc",
                 anchor="w").pack(fill="x", padx=8, pady=(6, 0))

    def _btn(self, text, cmd, variant="normal"):
        colors = {
            "primary": ("#0e639c", "white"),
            "warning": ("#8b4513", "white"),
            "success": ("#1a6b3c", "white"),
            "normal":  ("#3c3c3c", "#cccccc"),
        }
        bg, fg = colors.get(variant, colors["normal"])
        tk.Button(self, text=text, command=cmd,
                  bg=bg, fg=fg, relief="flat", anchor="w",
                  padx=8).pack(fill="x", padx=8, pady=2)

    def _build(self):
        self._lbl("Logo Mask Painter", font=("", 10, "bold"))
        self._lbl("─" * 22)

        self._lbl("Modo de pintura")
        self._btn("🖌  Pintar  (clique-esq)", self.app.set_paint, "primary")
        self._btn("🧹 Apagar  (clique-dir)", self.app.set_erase)

        self._lbl("Tamanho do pincel")
        self.brush_lbl = tk.StringVar(value="20px")
        tk.Label(self, textvariable=self.brush_lbl, bg="#1e1e1e",
                 fg="#56a0d3").pack(fill="x", padx=8)
        self._btn("Menor", self.app.brush_smaller)
        self._btn("Maior", self.app.brush_bigger)

        self._lbl("Zoom")
        self._btn("Zoom In   (scroll ↑)", self.app.zoom_in)
        self._btn("Zoom Out  (scroll ↓)", self.app.zoom_out)
        self._btn("1:1 Reset zoom", self.app.zoom_reset)

        self._lbl("─" * 22)
        self._btn("Desfazer  (Ctrl+Z)", self.app.undo)
        self._btn("Limpar máscara  (C)", self.app.clear_mask, "warning")

        self._lbl("─" * 22)
        self._btn("Criar máscara do zero", self.app.criar_mascara)
        self._btn("Salvar preview (P)", self.app.preview_mask)
        self._btn("Enviar IOPaint (S)", self.app.send_to_iopaint, "success")

        self._lbl("─" * 22)
        self._lbl("Status:")
        self.status_lbl = tk.StringVar(value="Abra uma imagem →")
        tk.Label(self, textvariable=self.status_lbl, bg="#1e1e1e",
                 fg="#4ec94e", anchor="w", wraplength=140,
                 justify="left").pack(fill="x", padx=8)

        self._lbl(" ")
        self._lbl("Instruções:", font=("", 8))
        self._lbl("• Esq: pintar\n• Dir: apagar\n• Scroll: zoom\n"
                  "• Ctrl+Z: desfazer\n• C: limpar\n• S: enviar IOPaint",
                  font=("", 8), fg="#888888")


class LogoPainterApp:
    def __init__(self, root: tk.Tk, folder: str, iopaint_url: str):
        self.root = root
        self.root.title("Logo Mask Painter")
        self.root.geometry("1280x800")
        self.folder = Path(folder).resolve()
        self.iopaint_url = iopaint_url.rstrip("/")
        self._current_path: Optional[Path] = None
        self._last_result: Optional[PILImage.Image] = None

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        self._info_var = tk.StringVar(value="Selecione uma imagem na árvore →")
        tk.Label(self.root, textvariable=self._info_var, anchor="w",
                 bg="#252526", fg="#858585").pack(fill="x")

        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True)

        self._side = SidePanel(main, self, width=165)
        self._side.pack(side="left", fill="y")
        self._side.pack_propagate(False)

        self._canvas_widget = MaskCanvas(
            main,
            on_status=self._set_status,
            on_brush_info=lambda msg: self._side.brush_lbl.set(msg),
        )
        self._canvas_widget.pack(side="left", fill="both", expand=True)

        self._tree = ImageTree(
            main,
            self.folder,
            on_file_selected=self._open_image,
            width=240,
        )
        self._tree.pack(side="left", fill="y")
        self._tree.pack_propagate(False)

    def _bind_keys(self):
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<c>", lambda e: self.clear_mask())
        self.root.bind("<p>", lambda e: self.preview_mask())
        self.root.bind("<s>", lambda e: self.send_to_iopaint())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in())
        self.root.bind("<Control-minus>", lambda e: self.zoom_out())
        self.root.bind("<Control-0>", lambda e: self.zoom_reset())

    def _set_status(self, msg: str):
        self._side.status_lbl.set(msg)

    def _set_info(self, msg: str):
        self._info_var.set(msg)

    def _open_image(self, path: Path):
        if path.suffix.lower() not in IMAGE_EXTS:
            return
        self._current_path = path
        self._canvas_widget.load_image(path)
        self._set_info(f" {path.name}  |  Esq=pintar  Dir=apagar  Scroll=zoom")
        self._set_status(f"Aberto: {path.name}")

    def set_paint(self):
        self._canvas_widget.erase_mode = False
        self._set_status("Modo: Pintar")

    def set_erase(self):
        self._canvas_widget.erase_mode = True
        self._set_status("Modo: Apagar")

    def brush_smaller(self):
        self._canvas_widget.brush_size = max(
            2, self._canvas_widget.brush_size - 5)
        self._side.brush_lbl.set(
            f"{self._canvas_widget.brush_size}px  zoom:{self._canvas_widget.zoom:.1f}×")

    def brush_bigger(self):
        self._canvas_widget.brush_size = min(
            200, self._canvas_widget.brush_size + 10)
        self._side.brush_lbl.set(
            f"{self._canvas_widget.brush_size}px  zoom:{self._canvas_widget.zoom:.1f}×")

    def zoom_in(self):
        self._canvas_widget.zoom_in()

    def zoom_out(self):
        self._canvas_widget.zoom_out()

    def zoom_reset(self):
        self._canvas_widget.zoom_reset()

    def undo(self):
        self._canvas_widget.undo()

    def clear_mask(self):
        self._canvas_widget.clear_mask()

    def criar_mascara(self):
        if self._canvas_widget.orig:
            w, h = self._canvas_widget.orig.size
        else:
            w, h = 800, 600

        def on_mask_ready(mask: PILImage.Image):
            path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Salvar máscara",
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("Todos", "*.*")],
                initialfile="mascara.png",
            )
            if path:
                mask.save(path)
                self._set_status(f"Máscara salva: {Path(path).name}")
                messagebox.showinfo(
                    "Salvo", f"Máscara salva em:\n{path}", parent=self.root)

        CriarMascaraDialog(
            self.root, callback=on_mask_ready, width=w, height=h)

    def preview_mask(self):
        if self._canvas_widget.mask is None or self._current_path is None:
            messagebox.showwarning(
                "Aviso", "Nenhuma imagem aberta.", parent=self.root)
            return
        mask = self._canvas_widget.get_mask()
        out = self._current_path.parent / \
            f"{self._current_path.stem}_mask_preview.png"
        mask.save(out)
        self._set_status(f"Preview salvo: {out.name}")
        messagebox.showinfo(
            "Preview", f"Máscara salva em:\n{out}", parent=self.root)

    def send_to_iopaint(self):
        if self._canvas_widget.orig is None or self._current_path is None:
            messagebox.showwarning(
                "Aviso", "Abra uma imagem primeiro.", parent=self.root)
            return
        orig = self._canvas_widget.get_orig()
        mask = self._canvas_widget.get_mask()
        if orig is None or mask is None:
            return

        self._set_status("Enviando…")
        self.root.update_idletasks()

        def _worker():
            img_buf = io.BytesIO()
            orig.convert("RGB").save(img_buf, format="PNG")
            img_buf.seek(0)

            mask_buf = io.BytesIO()
            mask.save(mask_buf, format="PNG")
            mask_buf.seek(0)

            url = f"{self.iopaint_url}/api/v1/inpaint"
            try:
                resp = requests.post(
                    url,
                    files={
                        "image": ("image.png", img_buf, "image/png"),
                        "mask": ("mask.png", mask_buf, "image/png"),
                    },
                    timeout=120,
                )
                if resp.status_code == 200:
                    result_img = PILImage.open(
                        io.BytesIO(resp.content)).convert("RGB")
                    self._last_result = result_img
                    self.root.after(
                        0, lambda: self._on_iopaint_success(result_img))
                else:
                    msg = f"Erro HTTP {resp.status_code}\n{resp.text[:200]}"
                    self.root.after(0, lambda: self._on_iopaint_error(msg))
            except requests.exceptions.ConnectionError:
                msg = f"Não conectou em {self.iopaint_url}\nVerifique se o IOPaint está rodando."
                self.root.after(0, lambda: self._on_iopaint_error(msg))
            except Exception as e:
                self.root.after(0, lambda: self._on_iopaint_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_iopaint_success(self, result_img: PILImage.Image):
        self._set_status("Concluído!")
        dlg = SaveResultDialog(self.root, result_img, self._current_path)
        if dlg.choice:
            action, path = dlg.choice
            if action == "discard":
                self._set_status("Descartado — edite mais e tente novamente")
            elif path:
                self._set_status(f"Salvo: {path.name}")
                if action == "overwrite" and self._current_path:
                    self._open_image(self._current_path)

    def _on_iopaint_error(self, msg: str):
        self._set_status("Erro")
        messagebox.showerror("IOPaint", msg, parent=self.root)


def main():
    parser = argparse.ArgumentParser(
        description="Logo Mask Painter — pinte a logo e envie ao IOPaint"
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Pasta com as imagens (padrão: pasta atual)",
    )
    parser.add_argument(
        "--iopaint-url",
        default="http://localhost:8080",
        help="URL base do IOPaint (padrão: http://localhost:8080)",
    )
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.is_dir():
        print(f"Erro: '{folder}' não é uma pasta.", file=sys.stderr)
        sys.exit(1)

    root = tk.Tk()
    app = LogoPainterApp(root, folder=str(
        folder), iopaint_url=args.iopaint_url)
    root.mainloop()


if __name__ == "__main__":
    main()
