"""
INTERFAZ GRÁFICA - Sistema de Registro de Eventos (Simposio)  ·  versión rediseñada
Colócalo junto a automata.py, database.py y conexionDataBase.py y ejecuta:  python interfaz.py

Navegación lateral:
  Procesar · Revisión manual · Emitir QRs · Puerta · Rechazados · Base de QRs
"""
import csv
import math
import os
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

from automata import qrDbMng, AFDValidador

try:  # texto nítido en pantallas con escala de Windows
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

SESIONES = 2  # días / subeventos del simposio

# ---------- paleta (imagen de referencia) ----------
PRIMARY = "#005187"
MID = "#4d82bc"
LIGHT = "#84b6f4"
SOFT = "#c4dafa"
BG = "#fcffff"
# apoyo
TEXT = "#0b2a43"
MUTED = "#6b86a0"
BORDE = "#d6e4f8"
SOMBRA = "#e6eefa"
OK = "#2e9e6b"
ERR = "#d64545"
ZEBRA = "#f4f8fe"

FUENTE = "Segoe UI"
ESC = 1.0
F_BTN = ("Segoe UI", 12, "bold")
# Fuentes redondeadas / amigables, en orden de preferencia (se usa la primera instalada).
# Para el mejor resultado instala "Nunito" (gratis en Google Fonts).
PREFERIDAS = [("Nunito", 1.0), ("Quicksand", 1.0), ("Poppins", 0.93), ("Candara", 1.12),
              ("Calibri", 1.12), ("Trebuchet MS", 1.0), ("Segoe UI", 1.0)]


def F(size, bold=False):
    """Fuente de la interfaz, ajustada al tamaño visual de la familia elegida."""
    t = [FUENTE, max(1, round(size * ESC))]
    if bold:
        t.append("bold")
    return tuple(t)


def elegir_fuente():
    global FUENTE, ESC, F_BTN
    disponibles = {f.lower(): f for f in tkfont.families()}
    for nombre, esc in PREFERIDAS:
        if nombre.lower() in disponibles:
            FUENTE, ESC = disponibles[nombre.lower()], esc
            break
    F_BTN = F(12, True)


# ==========================================
# UTILIDADES GRÁFICAS
# ==========================================
def _rgb(c):
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def lerp(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rrect(cv, x1, y1, x2, y2, r, **kw):
    """Rectángulo redondeado en un Canvas."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    p = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
         x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(p, smooth=True, **kw)


def animar(w, ms, paso, fin=None):
    """Anima `paso(e)` con e de 0 a 1 (ease-out). Devuelve un handle cancelable."""
    h = {"on": True}
    t0 = time.perf_counter()

    def tick():
        if not h["on"]:
            return
        t = min((time.perf_counter() - t0) * 1000 / ms, 1.0)
        try:
            paso(1 - (1 - t) ** 3)
            if t < 1:
                w.after(15, tick)
            elif fin:
                fin()
        except tk.TclError:
            pass

    tick()
    return h


def cancelar(h):
    if h:
        h["on"] = False


# ==========================================
# WIDGETS PERSONALIZADOS
# ==========================================
ESTILOS = {
    "primary": dict(bg=PRIMARY, hover=MID, fg="#ffffff"),
    "secondary": dict(bg=SOFT, hover=LIGHT, fg=PRIMARY),
    "danger": dict(bg="#fde7e7", hover="#f7b9b9", fg="#a02323"),
    "success": dict(bg=OK, hover="#38b27d", fg="#ffffff"),
    "nav": dict(bg=PRIMARY, hover="#1a6aa3", fg=SOFT),
    "nav_on": dict(bg=SOFT, hover=SOFT, fg=PRIMARY),
}


class RoundButton(tk.Canvas):
    """Píldora que cambia de color, crece levemente al pasar el mouse y se hunde al hacer clic."""
    REPOSO = 2  # margen en reposo; al pasar el mouse baja a 0 (el botón "crece")

    def __init__(self, parent, text, command=None, style="primary", width=None, height=54,
                 align="center", radius=None, bg=None, icon=None):
        bg = bg or parent.cget("bg")
        fnt = tkfont.Font(font=F_BTN)
        super().__init__(parent, width=width or fnt.measure(text) + 64, height=height, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.command, self.align, self.radio, self.icono = command, align, radius or height // 2, icon
        self.texto, self.style = text, style
        self.fill, self.fg = ESTILOS[style]["bg"], ESTILOS[style]["fg"]
        self.inset, self.dx, self._h, self._sobre = self.REPOSO, 0, None, False
        self.bind("<Configure>", lambda e: self._dibujar())
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)

    def _dibujar(self):
        w, h, i = self.winfo_width(), self.winfo_height(), self.inset
        self.delete("all")
        rrect(self, 1 + i, 1 + i, w - 1 - i, h - 1 - i, self.radio, fill=self.fill, outline="", tags="r")
        if self.align == "center":
            self.create_text(w / 2, h / 2, text=self.texto, fill=self.fg, font=F_BTN, tags="t")
        elif self.icono:  # icono y texto en columnas fijas para que todo quede alineado
            self.create_text(40 + self.dx, h / 2, text=self.icono, fill=self.fg, font=F_BTN, tags="t")
            self.create_text(68 + self.dx, h / 2, text=self.texto, fill=self.fg, font=F_BTN, anchor="w", tags="t")
        else:
            self.create_text(26 + self.dx, h / 2, text=self.texto, fill=self.fg, font=F_BTN, anchor="w", tags="t")

    def _ir(self, fill, fg, inset, dx, ms=200):
        f0, g0, i0, d0 = self.fill, self.fg, self.inset, self.dx
        cancelar(self._h)

        def paso(e):
            self.fill, self.fg = lerp(f0, fill, e), lerp(g0, fg, e)
            self.inset, self.dx = i0 + (inset - i0) * e, d0 + (dx - d0) * e
            self._dibujar()
        self._h = animar(self, ms, paso)

    def _hover(self, on):
        self._sobre = on
        e = ESTILOS[self.style]
        self._ir(e["hover"] if on else e["bg"], e["fg"], 0 if on else self.REPOSO,
                 6 if (on and self.align == "left") else 0)

    def set_style(self, style):
        self.style = style
        e = ESTILOS[style]
        self._ir(e["hover"] if self._sobre else e["bg"], e["fg"], self.inset, self.dx, 240)

    def _press(self, e):
        cancelar(self._h)
        self.inset = 4
        self._dibujar()

    def _release(self, e):
        self.inset = 0 if self._sobre else self.REPOSO
        self._dibujar()
        if 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height() and self.command:
            self.command()


class Card(tk.Canvas):
    """Tarjeta blanca redondeada con sombra suave. Los hijos van en `.body`."""

    def __init__(self, parent, height=10, pad=20, radio=26, bg=None):
        super().__init__(parent, width=10, height=height, bg=bg or parent.cget("bg"),
                         highlightthickness=0, bd=0)
        self.pad, self.radio = pad, radio
        self.body = tk.Frame(self, bg="white")
        self._win = self.create_window(pad + 2, pad + 2, window=self.body, anchor="nw")
        self.bind("<Configure>", self._dibujar)

    def _dibujar(self, e):
        w, h = e.width, e.height
        self.delete("fondo")
        rrect(self, 4, 7, w - 1, h - 1, self.radio, fill=SOMBRA, outline="", tags="fondo")
        rrect(self, 2, 2, w - 4, h - 5, self.radio, fill="white", outline=BORDE, tags="fondo")
        self.tag_lower("fondo")
        self.itemconfigure(self._win, width=max(w - 2 * self.pad - 6, 1), height=max(h - 2 * self.pad - 9, 1))


class RoundEntry(tk.Canvas):
    """Campo de texto redondeado; el borde se ilumina al enfocar."""

    def __init__(self, parent, height=52, font=None, bg=None):
        super().__init__(parent, width=10, height=height, bg=bg or parent.cget("bg"),
                         highlightthickness=0, bd=0)
        self.borde, self._h = BORDE, None
        self.entry = tk.Entry(self, font=font or F(12), bd=0, relief="flat", bg="white", fg=TEXT,
                              insertbackground=PRIMARY, highlightthickness=0)
        self._win = self.create_window(22, height / 2, window=self.entry, anchor="w")
        self.bind("<Configure>", lambda e: self._dibujar())
        self.entry.bind("<FocusIn>", lambda e: self._foco(MID))
        self.entry.bind("<FocusOut>", lambda e: self._foco(BORDE))

    def _dibujar(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("b")
        rrect(self, 2, 2, w - 2, h - 2, h // 2, fill="white", outline=self.borde, width=2, tags="b")
        self.tag_lower("b")
        self.coords(self._win, 24, h / 2)
        self.itemconfigure(self._win, width=max(w - 48, 10))

    def _foco(self, destino):
        o = self.borde
        cancelar(self._h)

        def paso(e):
            self.borde = lerp(o, destino, e)
            self.itemconfigure("b", outline=self.borde)
        self._h = animar(self, 180, paso)

    def get(self):
        return self.entry.get()

    def limpiar(self):
        self.entry.delete(0, "end")

    def focus_set(self):
        self.entry.focus_set()

    def on_return(self, cb):
        self.entry.bind("<Return>", lambda e: cb())


class Segmented(tk.Frame):
    """Grupo de botones tipo píldora para elegir una opción."""

    def __init__(self, parent, opciones, valor, on_change=None, height=48):
        super().__init__(parent, bg=parent.cget("bg"))
        self.on_change, self.valor, self.btns = on_change, valor, {}
        for o in opciones:
            b = RoundButton(self, str(o), lambda o=o: self.set(o), "primary" if o == valor else "secondary",
                            height=height)
            b.pack(side="left", padx=(0, 8))
            self.btns[o] = b

    def set(self, v):
        self.valor = v
        for o, b in self.btns.items():
            b.set_style("primary" if o == v else "secondary")
        if self.on_change:
            self.on_change(v)


class Banner(tk.Canvas):
    """Panel grande de resultado (puerta) con transición de color y pequeño rebote."""
    ESTADOS = {"ok": (OK, "#ffffff", "✔"), "err": (ERR, "#ffffff", "✖"), "idle": (SOFT, PRIMARY, "")}

    def __init__(self, parent, height=170):
        super().__init__(parent, height=height, bg=parent.cget("bg"), highlightthickness=0, bd=0)
        self.fill, self.fg, self.icono, self.msg, self.dy = SOFT, PRIMARY, "", "ESPERANDO QR", 0
        self._h = self._t = None
        self.bind("<Configure>", lambda e: self._dibujar())

    def _dibujar(self):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("all")
        rrect(self, 2, 2, w - 2, h - 2, 38, fill=self.fill, outline="")
        if self.icono:
            self.create_text(w / 2, h * 0.34 + self.dy, text=self.icono, fill=self.fg, font=F(40, True))
        self.create_text(w / 2, h * 0.74 if self.icono else h / 2, text=self.msg, fill=self.fg, width=w - 80,
                         justify="center", font=F(16 if self.icono else 22, True))

    def mostrar(self, tipo, msg):
        fill, fg, icono = self.ESTADOS[tipo]
        f0, g0 = self.fill, self.fg
        self.icono, self.msg = icono, msg
        cancelar(self._h)
        if self._t:
            self.after_cancel(self._t)
            self._t = None

        def paso(e):
            self.fill, self.fg = lerp(f0, fill, e), lerp(g0, fg, e)
            self.dy = -14 * math.sin(math.pi * e)
            self._dibujar()
        self._h = animar(self, 380, paso)
        if tipo != "idle":
            self._t = self.after(4500, lambda: self.mostrar("idle", "ESPERANDO QR"))


# ==========================================
# TABLAS
# ==========================================
def estilos_ttk():
    st = ttk.Style()
    st.theme_use("clam")
    st.configure("Treeview", background="white", fieldbackground="white", foreground=TEXT, rowheight=40,
                 borderwidth=0, font=F(10))
    st.configure("Treeview.Heading", background=SOFT, foreground=PRIMARY, font=F(10, True),
                 relief="flat", padding=(12, 11), borderwidth=0)
    st.map("Treeview", background=[("selected", LIGHT)], foreground=[("selected", PRIMARY)])
    st.map("Treeview.Heading", background=[("active", LIGHT)])
    st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    st.configure("Vertical.TScrollbar", background=SOFT, troughcolor="white", bordercolor="white",
                 arrowcolor=PRIMARY, lightcolor="white", darkcolor="white", relief="flat", gripcount=0)
    st.map("Vertical.TScrollbar", background=[("active", LIGHT)])


def crear_tabla(padre, columnas):
    """columnas: [(id, titulo, ancho)] → (frame, tree). Las columnas se estiran con la ventana."""
    marco = tk.Frame(padre, bg="white")
    tree = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", selectmode="browse")
    for cid, titulo, ancho in columnas:
        tree.heading(cid, text=titulo, anchor="w")
        tree.column(cid, width=ancho, minwidth=50, anchor="w", stretch=True)
    sb = ttk.Scrollbar(marco, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.tag_configure("par", background="white")
    tree.tag_configure("impar", background=ZEBRA)
    sb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    return marco, tree


def vaciar(tree):
    tree.delete(*tree.get_children())


def insertar(tree, valores, iid=None, pos="end"):
    tag = "par" if len(tree.get_children()) % 2 == 0 else "impar"
    kw = {"iid": iid} if iid is not None else {}
    tree.insert("", pos, values=valores, tags=(tag,), **kw)


def llenar(tree, filas, paso=24, max_anim=12):
    """Reemplaza el contenido con una pequeña cascada. filas: [(valores, iid o None)]"""
    vaciar(tree)
    tok = tree._tok = object()

    def poner(i):
        if tree._tok is not tok:
            return
        while i < len(filas):
            v, iid = filas[i]
            insertar(tree, v, iid=iid)
            i += 1
            if i <= max_anim:
                tree.after(paso, lambda: poner(i))
                return
    poner(0)


# ==========================================
# APLICACIÓN
# ==========================================
class App:
    PAGINAS = [("procesar", "⚡", "Procesar"), ("revision", "✎", "Revisión manual"),
               ("emitir", "▣", "Emitir QRs"), ("puerta", "⇥", "Puerta"),
               ("rechazados", "⚠", "Rechazados"), ("base", "☰", "Base de QRs")]

    def __init__(self, root):
        self.root = root
        root.title("Registro de Eventos URL")
        root.geometry("1220x780")
        root.minsize(1000, 660)
        root.configure(bg=BG)
        estilos_ttk()

        self.lock = threading.Lock()
        self.busy, self._pulsando = 0, False
        self.mng = qrDbMng(sesiones=SESIONES)
        self.validador = AFDValidador(sesiones=SESIONES)
        self.pend, self.listos, self.rechazados = [], [], []
        self.dia = 1
        self.paginas, self.navs, self.actual, self._pg_h = {}, {}, None, None

        self._sidebar()
        self.stage = tk.Frame(root, bg=BG)
        self.stage.pack(side="left", fill="both", expand=True)

        for clave, _, _ in self.PAGINAS:
            p = tk.Frame(self.stage, bg=BG)
            self.paginas[clave] = p
            getattr(self, f"_pg_{clave}")(p)

        self.actual = "procesar"
        self.paginas["procesar"].place(relx=0, rely=0, relwidth=1, relheight=1)
        self.navs["procesar"].set_style("nav_on")
        root.after(150, self.actualizar_resumen)

    # ---------- estructura ----------
    def _sidebar(self):
        sb = tk.Frame(self.root, bg=PRIMARY, width=250)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        self._logo(sb)
        tk.Label(sb, text="Registro de Eventos URL", font=F(17, True), fg="white", bg=PRIMARY,
                 wraplength=200, justify="left").pack(anchor="w", padx=28, pady=(16, 26))
        for clave, icono, nombre in self.PAGINAS:
            b = RoundButton(sb, nombre, lambda c=clave: self.ir(c), "nav", height=52,
                            align="left", radius=20, icon=icono)
            b.pack(fill="x", padx=16, pady=4)
            self.navs[clave] = b
        estado = tk.Frame(sb, bg=PRIMARY)
        estado.pack(side="bottom", fill="x", padx=24, pady=26)
        self.dot = tk.Canvas(estado, width=14, height=14, bg=PRIMARY, highlightthickness=0)
        self.dot.create_oval(2, 2, 12, 12, fill="#5fd6a0", outline="", tags="d")
        self.dot.pack(side="left")
        self.lbl_estado = tk.Label(estado, text="Listo", font=F(10), fg=SOFT, bg=PRIMARY,
                                   wraplength=180, justify="left")
        self.lbl_estado.pack(side="left", padx=10)

    def _logo(self, sb):
        """Logo de la universidad en una tarjeta blanca redondeada (se ve bien sobre el azul)."""
        W, H = 210, 100
        cv = tk.Canvas(sb, width=W, height=H, bg=PRIMARY, highlightthickness=0, bd=0)
        cv.pack(padx=20, pady=(30, 0))
        rrect(cv, 2, 2, W - 2, H - 2, 28, fill=BG, outline="")
        ruta = next((os.path.join(b, "logo.png") for b in (os.path.dirname(os.path.abspath(__file__)), os.getcwd())
                     if os.path.exists(os.path.join(b, "logo.png"))), None)
        try:
            if not ruta:
                raise FileNotFoundError("no se encontró logo.png junto a interfaz.py")
            self.logo_img = self._cargar_logo(ruta, W - 50, H - 34)
            cv.create_image(W / 2, H / 2, image=self.logo_img)
        except Exception as e:
            print("Logo no cargado:", e)
            cv.create_text(W / 2, H / 2, text="URL", fill=PRIMARY, font=F(28, True))

    @staticmethod
    def _cargar_logo(ruta, mw, mh):
        try:
            from PIL import Image, ImageTk  # reducción suave si Pillow está instalado
            im = Image.open(ruta).convert("RGBA")
            im.thumbnail((mw, mh), Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except ImportError:
            img = tk.PhotoImage(file=ruta)
            f = max(1, math.ceil(img.width() / mw), math.ceil(img.height() / mh))
            return img.subsample(f) if f > 1 else img

    def ir(self, nombre):
        if nombre == self.actual:
            return
        nuevo, viejo = self.paginas[nombre], self.paginas[self.actual]
        cancelar(self._pg_h)
        for p in self.paginas.values():
            if p is not viejo and p is not nuevo:
                p.place_forget()
        for k, b in self.navs.items():
            b.set_style("nav_on" if k == nombre else "nav")
        nuevo.place(relx=0.05, rely=0, relwidth=1, relheight=1)
        nuevo.lift()

        def fin():
            viejo.place_forget()
            nuevo.place_configure(relx=0)
        self._pg_h = animar(self.stage, 320, lambda e: nuevo.place_configure(relx=0.05 * (1 - e)), fin)
        self.actual = nombre
        self._al_abrir(nombre)

    def _al_abrir(self, nombre):
        if nombre == "revision":
            self.cargar_pendientes()
        elif nombre == "rechazados":
            self.cargar_rechazados()
        elif nombre == "base":
            self.cargar_base()
        elif nombre == "puerta":
            self.ent_qr.focus_set()
        elif nombre == "procesar":
            self.actualizar_resumen()

    def _cabecera(self, p, titulo, sub):
        f = tk.Frame(p, bg=BG)
        f.pack(fill="x", padx=38, pady=(32, 16))
        tk.Label(f, text=titulo, font=F(26, True), fg=PRIMARY, bg=BG).pack(anchor="w")
        tk.Label(f, text=sub, font=F(11), fg=MUTED, bg=BG).pack(anchor="w")
        cuerpo = tk.Frame(p, bg=BG)
        cuerpo.pack(fill="both", expand=True, padx=38, pady=(0, 32))
        return cuerpo

    @staticmethod
    def _titulo(padre, texto):
        tk.Label(padre, text=texto, font=F(13, True), fg=PRIMARY, bg="white").pack(anchor="w", pady=(0, 10))

    # ---------- trabajo en segundo plano ----------
    def bg(self, fn, ok=None, msg="Trabajando…", excl=False):
        self.busy += 1
        self.lbl_estado.config(text=msg)
        if not self._pulsando:
            self._pulsando = True
            self._pulso()

        def fin():
            self.busy -= 1
            if self.busy <= 0:
                self.lbl_estado.config(text="Listo")

        def trabajo():
            try:
                if excl:
                    with self.lock:
                        r = fn()
                else:
                    r = fn()
            except Exception as e:
                self.root.after(0, lambda e=e: (fin(), self._fallo(e)))
                return
            self.root.after(0, lambda: (fin(), ok(r) if ok else None))

        threading.Thread(target=trabajo, daemon=True).start()

    def _pulso(self):
        if self.busy <= 0:
            self.dot.itemconfigure("d", fill="#5fd6a0")
            self._pulsando = False
            return
        t = (math.sin(time.perf_counter() * 6) + 1) / 2
        self.dot.itemconfigure("d", fill=lerp(MID, "#ffffff", t))
        self.root.after(40, self._pulso)

    def _fallo(self, e):
        self.lbl_estado.config(text="Error")
        messagebox.showerror("Error", str(e))

    def log(self, texto):
        self.txt_log.insert("end", f"{datetime.now():%H:%M:%S}  ", "hora")
        self.txt_log.insert("end", texto + "\n")
        self.txt_log.see("end")

    # ==========================================
    # PÁGINA: PROCESAR
    # ==========================================
    def _pg_procesar(self, p):
        c = self._cabecera(p, "Procesar recibos", "Pasa los recibos pendientes por el autómata de validación")
        fila = tk.Frame(c, bg=BG)
        fila.pack(fill="x")
        RoundButton(fila, "▶   Procesar recibos pendientes", self.procesar, height=58).pack(side="left")
        RoundButton(fila, "↻   Actualizar", self.actualizar_resumen, "secondary", height=58).pack(side="left", padx=12)

        stats = tk.Frame(c, bg=BG)
        stats.pack(fill="x", pady=18)
        self.stat = {}
        for i, (k, t) in enumerate([("rev", "En revisión manual"), ("sin", "Estudiantes sin aceptar"),
                                    ("qr", "QRs emitidos")]):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            card = Card(stats, height=150, pad=18)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 9, 0 if i == 2 else 9))
            tk.Label(card.body, text=t, font=F(10), fg=MUTED, bg="white").pack(anchor="w")
            self.stat[k] = tk.Label(card.body, text="–", font=F(32, True), fg=PRIMARY, bg="white")
            self.stat[k].pack(anchor="w")

        card = Card(c)
        card.pack(fill="both", expand=True)
        self._titulo(card.body, "Registro de actividad")
        self.txt_log = tk.Text(card.body, bd=0, relief="flat", font=("Consolas", 10), fg=TEXT, bg="white",
                               padx=4, pady=4, highlightthickness=0)
        self.txt_log.tag_configure("hora", foreground=MID)
        self.txt_log.pack(fill="both", expand=True)

    def contar(self, lbl, destino):
        try:
            ini = int(lbl.cget("text"))
        except ValueError:
            ini = 0
        animar(lbl, 700, lambda e: lbl.config(text=str(int(ini + (destino - ini) * e))),
               lambda: lbl.config(text=str(destino)))

    def actualizar_resumen(self):
        def calc():
            return (len(self.mng.manual.facturas_pendientes()),
                    len(self.mng.manual.estudiantes_sin_aceptar()),
                    len(self.mng.obtener_base_qr()))

        def ok(r):
            for i, (k, v) in enumerate(zip(("rev", "sin", "qr"), r)):
                self.root.after(i * 130, lambda k=k, v=v: self.contar(self.stat[k], v))
        self.bg(calc, ok, "Actualizando resumen…")

    def procesar(self):
        def ok(r):
            self.log(r["mensaje"])
            for m in r["mensajes"]:
                self.log("   · " + m)
            if r.get("detalle"):
                self.log("   ⚠ " + r["detalle"])
            self.actualizar_resumen()
        self.bg(self.mng.procesar_pendientes, ok, "Procesando recibos…", excl=True)

    # ==========================================
    # PÁGINA: REVISIÓN MANUAL
    # ==========================================
    def _pg_revision(self, p):
        c = self._cabecera(p, "Revisión manual", "Decide a quién corresponde cada recibo dudoso")
        c.grid_columnconfigure(0, weight=5, uniform="r")
        c.grid_columnconfigure(1, weight=6, uniform="r")
        c.grid_rowconfigure(0, weight=1)

        izq = Card(c)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._titulo(izq.body, "Recibos en revisión")
        RoundButton(izq.body, "↻   Recargar", self.cargar_pendientes, "secondary", height=50).pack(side="bottom", anchor="w", pady=(12, 0))
        m, self.t_pend = crear_tabla(izq.body, [("id", "Recibo", 70), ("nombre", "A nombre de", 200), ("motivo", "Motivo", 70)])
        m.pack(fill="both", expand=True)
        self.t_pend.bind("<<TreeviewSelect>>", lambda e: self.mostrar_candidatos())

        der = Card(c)
        der.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self._titulo(der.body, "Candidatos")
        acc = tk.Frame(der.body, bg="white")
        acc.pack(side="bottom", fill="x", pady=(12, 0))
        RoundButton(acc, "✔   Aceptar seleccionado", self.aceptar_sel, "primary", height=56).pack(side="left")
        RoundButton(acc, "✖   Rechazar", self.rechazar, "danger", height=56).pack(side="left", padx=10)
        car = tk.Frame(der.body, bg="white")
        car.pack(side="bottom", fill="x", pady=(10, 0))
        self.e_carnet = RoundEntry(car, height=50)
        self.e_carnet.pack(side="left", fill="x", expand=True)
        RoundButton(car, "Aceptar por carnet", self.aceptar_carnet, "secondary", height=50).pack(side="left", padx=(10, 0))
        bus = tk.Frame(der.body, bg="white")
        bus.pack(side="bottom", fill="x", pady=(12, 0))
        self.e_buscar = RoundEntry(bus, height=50)
        self.e_buscar.pack(side="left", fill="x", expand=True)
        self.e_buscar.on_return(self.buscar)
        RoundButton(bus, "Buscar nombre", self.buscar, "secondary", height=50).pack(side="left", padx=(10, 0))
        m, self.t_cand = crear_tabla(der.body, [("carnet", "Carnet", 90), ("nombre", "Nombre", 220),
                                                ("pct", "%", 50), ("est", "Estado", 100)])
        m.pack(fill="both", expand=True)

    def cargar_pendientes(self):
        def ok(lista):
            self.pend = lista
            vaciar(self.t_cand)
            llenar(self.t_pend, [((f["id_pago"], f["nombre"], f["motivo"]), str(f["id_pago"])) for f in lista])
        self.bg(self.mng.manual.facturas_pendientes, ok, "Cargando recibos…")

    def _factura_sel(self):
        sel = self.t_pend.selection()
        if not sel:
            messagebox.showinfo("Revisión", "Selecciona un recibo de la lista izquierda.")
            return None
        return next((f for f in self.pend if str(f["id_pago"]) == sel[0]), None)

    def mostrar_candidatos(self):
        vaciar(self.t_cand)
        sel = self.t_pend.selection()
        f = next((x for x in self.pend if sel and str(x["id_pago"]) == sel[0]), None)
        if not f:
            return
        llenar(self.t_cand, [((c["carnet"], c["nombre_completo"], c["puntaje"],
                               "YA VALIDADO" if c.get("ya_validado") else "Disponible"), str(i))
                             for i, c in enumerate(f["candidatos"])])

    def _cand_sel(self, f):
        sel = self.t_cand.selection()
        if not sel:
            messagebox.showinfo("Revisión", "Selecciona un candidato.")
            return None
        c = f["candidatos"][int(sel[0])]
        if c.get("ya_validado"):
            messagebox.showwarning("Revisión", "Ese estudiante ya fue validado con otro recibo.")
            return None
        return c

    def buscar(self):
        f = self._factura_sel()
        texto = self.e_buscar.get().strip()
        if not f or not texto:
            return

        def ok(res):
            conocidos = {c["carnet"] for c in f["candidatos"]}
            f["candidatos"] += [c for c in res if c["carnet"] not in conocidos]
            self.mostrar_candidatos()
        self.bg(lambda: self.mng.manual.buscar(texto), ok, "Buscando…")

    def _tras_decision(self, r):
        self.log(r["mensaje"])
        self.cargar_pendientes()

    def aceptar_sel(self):
        f = self._factura_sel()
        c = self._cand_sel(f) if f else None
        if c and messagebox.askyesno("Confirmar", f"¿Aceptar el recibo #{f['id_pago']} para\n{c['nombre_completo']} ({c['carnet']})?"):
            self.bg(lambda: self.mng.manual.aceptar(f["id_pago"], c["carnet"]), self._tras_decision, "Guardando…", True)

    def aceptar_carnet(self):
        f = self._factura_sel()
        carnet = self.e_carnet.get().strip()
        if f and carnet and messagebox.askyesno("Confirmar", f"¿Aceptar el recibo #{f['id_pago']} para el carnet {carnet}?"):
            self.bg(lambda: self.mng.manual.aceptar(f["id_pago"], carnet), self._tras_decision, "Guardando…", True)

    def rechazar(self):
        f = self._factura_sel()
        if not f:
            return
        motivo = "NM" if any(not c.get("ya_validado") for c in f["candidatos"]) else "NC"
        if messagebox.askyesno("Confirmar", f"¿Rechazar el recibo #{f['id_pago']}? (motivo {motivo})"):
            self.bg(lambda: self.mng.manual.rechazar(f["id_pago"], motivo), self._tras_decision, "Guardando…", True)

    # ==========================================
    # PÁGINA: EMITIR QRs
    # ==========================================
    def _pg_emitir(self, p):
        c = self._cabecera(p, "Emitir QRs", "Genera el código de cada estudiante aceptado")
        fila = tk.Frame(c, bg=BG)
        fila.pack(fill="x")
        RoundButton(fila, "⚙   Emitir QRs de los aceptados", self.emitir, height=58).pack(side="left")
        RoundButton(fila, "💾   Exportar CSV", self.exportar, "secondary", height=58).pack(side="left", padx=12)
        RoundButton(fila, "✔   Marcar como enviado", self.marcar_enviado, "secondary", height=58).pack(side="left")
        tk.Label(c, text="Las cadenas solo existen en esta pantalla: expórtalas antes de cerrar la aplicación.",
                 font=F(10), fg=ERR, bg=BG).pack(anchor="w", pady=(12, 12))
        card = Card(c)
        card.pack(fill="both", expand=True)
        m, self.t_emit = crear_tabla(card.body, [("carnet", "Carnet", 90), ("nombre", "Nombre", 230),
                                                 ("correo", "Correo", 220), ("cadena", "Cadena del QR", 360)])
        m.pack(fill="both", expand=True)

    def emitir(self):
        def ok(r):
            self.listos = r["listos"]
            llenar(self.t_emit, [((q["carnet"], q["nombre"], q["correo"], q["cadena"]), q["carnet"])
                                 for q in self.listos])
            msg = r["mensaje"]
            if r["fallidos"]:
                msg += "\nFallidos: " + "; ".join(f"{c} ({m})" for c, m in r["fallidos"])
            self.log(r["mensaje"])
            messagebox.showinfo("Emisión", msg)
        self.bg(self.mng.emitir_qrs, ok, "Emitiendo QRs…", True)

    def exportar(self):
        if not self.listos:
            messagebox.showinfo("Exportar", "No hay QRs emitidos en esta sesión.")
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="qrs_emitidos.csv")
        if ruta:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.DictWriter(fh, fieldnames=["carnet", "nombre", "correo", "cadena"])
                w.writeheader()
                w.writerows(self.listos)
            self.log(f"Exportados {len(self.listos)} QRs a {ruta}")

    def marcar_enviado(self):
        sel = self.t_emit.selection()
        if sel:
            self.bg(lambda: self.mng.confirmar_envio(sel[0]),
                    lambda _: (self.t_emit.delete(sel[0]), self.log(f"Carnet {sel[0]} marcado como enviado")), "Guardando…", True)

    # ==========================================
    # PÁGINA: PUERTA
    # ==========================================
    def _pg_puerta(self, p):
        c = self._cabecera(p, "Control de acceso", "Escanea el QR (el lector USB escribe y envía Enter automáticamente)")
        fila = tk.Frame(c, bg=BG)
        fila.pack(fill="x")
        Segmented(fila, [f"Día {i}" for i in range(1, SESIONES + 1)], "Día 1",
                  lambda v: (setattr(self, "dia", int(v.split()[1])), self.ent_qr.focus_set()), height=54).pack(side="left")
        self.ent_qr = RoundEntry(fila, height=54, font=("Consolas", 13))
        self.ent_qr.pack(side="left", fill="x", expand=True, padx=(16, 0))
        self.ent_qr.on_return(self.validar)
        self.banner = Banner(c)
        self.banner.pack(fill="x", pady=18)
        card = Card(c)
        card.pack(fill="both", expand=True)
        self._titulo(card.body, "Historial de ingresos")
        m, self.t_hist = crear_tabla(card.body, [("hora", "Hora", 80), ("dia", "Día", 50), ("carnet", "Carnet", 100),
                                                 ("res", "Resultado", 400), ("afd", "Traza AFD", 80)])
        m.pack(fill="both", expand=True)

    def validar(self):
        cadena = self.ent_qr.get().strip()
        self.ent_qr.limpiar()
        if not cadena:
            return
        r = self.validador.validar(cadena, self.dia)
        self.banner.mostrar("ok" if r["autorizado"] else "err", r["mensaje"])
        insertar(self.t_hist, (f"{datetime.now():%H:%M:%S}", self.dia, r["carnet"] or "—", r["mensaje"], r["entrada"]), pos=0)
        self.ent_qr.focus_set()

    # ==========================================
    # PÁGINA: RECHAZADOS
    # ==========================================
    def _pg_rechazados(self, p):
        c = self._cabecera(p, "Recibos rechazados", "Anomalías con los 5 estudiantes más probables")
        fila = tk.Frame(c, bg=BG)
        fila.pack(fill="x", pady=(0, 14))
        self.filtro = Segmented(fila, ["Todos", "MONTO", "NC", "NM"], "Todos", lambda v: self.cargar_rechazados())
        self.filtro.pack(side="left")
        RoundButton(fila, "↻   Recargar", self.cargar_rechazados, "secondary", height=48).pack(side="left", padx=4)
        det = Card(c, height=170)
        det.pack(side="bottom", fill="x", pady=(14, 0))
        self.txt_rech = tk.Text(det.body, bd=0, relief="flat", font=("Consolas", 10), fg=TEXT, bg="white", highlightthickness=0)
        self.txt_rech.pack(fill="both", expand=True)
        card = Card(c)
        card.pack(fill="both", expand=True)
        m, self.t_rech = crear_tabla(card.body, [("id", "Recibo", 60), ("no", "No. recibo", 100), ("nombre", "Pagador", 220),
                                                 ("monto", "Monto", 70), ("mot", "Motivo", 70), ("fecha", "Fecha", 150)])
        m.pack(fill="both", expand=True)
        self.t_rech.bind("<<TreeviewSelect>>", lambda e: self.detalle_rechazo())

    def cargar_rechazados(self):
        motivo = None if self.filtro.valor == "Todos" else self.filtro.valor

        def ok(filas):
            self.rechazados = filas
            llenar(self.t_rech, [((r["id_pago"], r["no_recibo"], r["nombre_pagador"], r["monto"], r["motivo"],
                                   r["fecha_rechazo"]), str(i)) for i, r in enumerate(filas)])
        self.bg(lambda: self.mng.manual.rechazados(motivo), ok, "Cargando rechazados…")

    def detalle_rechazo(self):
        sel = self.t_rech.selection()
        self.txt_rech.delete("1.0", "end")
        if not sel:
            return
        r = self.rechazados[int(sel[0])]
        self.txt_rech.insert("end", f"Candidatos probables para «{r['nombre_pagador']}»:\n")
        for c in r["candidatos"]:
            marca = "   [YA VINCULADO A OTRO RECIBO]" if c.get("ya_vinculado") else ""
            self.txt_rech.insert("end", f"  {c['carnet']:<12} {c['nombre_completo']:<40} {c['puntaje']}%{marca}\n")

    # ==========================================
    # PÁGINA: BASE DE QRs
    # ==========================================
    def _pg_base(self, p):
        c = self._cabecera(p, "Base de QRs", "Solo se guardan hashes SHA-256, nunca el código original")
        RoundButton(c, "↻   Recargar", self.cargar_base, "secondary", height=54).pack(anchor="w", pady=(0, 14))
        card = Card(c)
        card.pack(fill="both", expand=True)
        cols = [("carnet", "Carnet", 100), ("hash", "Hash (SHA-256)", 380), ("env", "Enviado", 70), ("fecha", "Emisión", 150)]
        cols += [(f"estado{i}", f"Día {i}", 60) for i in range(1, SESIONES + 1)]
        m, self.t_base = crear_tabla(card.body, cols)
        m.pack(fill="both", expand=True)

    def cargar_base(self):
        def ok(filas):
            def fila(r):
                v = [r["carnet"], r["codigo_hash"], "Sí" if r["enviado"] else "No", r["fecha_emision"]]
                return v + ["✔" if r.get(f"estado{i}") else "—" for i in range(1, SESIONES + 1)]
            llenar(self.t_base, [(fila(r), None) for r in filas])
        self.bg(self.mng.obtener_base_qr, ok, "Cargando base de QRs…")


if __name__ == "__main__":
    raiz = tk.Tk()
    elegir_fuente()
    App(raiz)
    raiz.mainloop()