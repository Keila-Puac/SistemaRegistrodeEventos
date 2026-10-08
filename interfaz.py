"""
INTERFAZ GRÁFICA - Sistema de Registro de Eventos (Simposio)
Colócalo en la misma carpeta que automata.py, database.py y conexionDataBase.py
y ejecútalo con:   python interfaz.py

Pestañas:
  1. Procesar     -> corre el AFND sobre los recibos pendientes
  2. Revisión     -> revisión manual (q6): aceptar / buscar / rechazar
  3. Emitir QRs   -> genera las cadenas de QR de los aceptados (y exporta CSV)
  4. Puerta       -> validación de ingreso (AFD); un lector de QR USB funciona como teclado
  5. Rechazados   -> anomalías con sus 5 candidatos probables
  6. Base de QRs  -> contenido de qr_externo.db (solo hashes)
"""
import csv
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

from automata import qrDbMng, AFDValidador

SESIONES = 2  # días / subeventos del simposio

VERDE, ROJO, GRIS = "#1b8a3a", "#c62828", "#37474f"


def crear_tabla(padre, columnas, alto=10):
    """Treeview con scroll. columnas: [(id, titulo, ancho)]"""
    marco = ttk.Frame(padre)
    tree = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings",
                        height=alto, selectmode="browse")
    for cid, titulo, ancho in columnas:
        tree.heading(cid, text=titulo)
        tree.column(cid, width=ancho, anchor="w")
    sb = ttk.Scrollbar(marco, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return marco, tree


def vaciar(tree):
    tree.delete(*tree.get_children())


class App:
    def __init__(self, root):
        self.root = root
        root.title("Sistema de Registro de Eventos · Simposio")
        root.geometry("1100x700")
        root.minsize(900, 600)

        self.lock = threading.Lock()
        self.mng = qrDbMng(sesiones=SESIONES)
        self.validador = AFDValidador(sesiones=SESIONES)
        self.pend = []        # facturas en revisión manual
        self.listos = []      # QRs emitidos en esta sesión
        self.rechazados = []

        self.status = tk.StringVar(value="Listo")
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        ttk.Label(root, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x", padx=8, pady=6)

        self._tab_procesar(nb)
        self._tab_revision(nb)
        self._tab_emitir(nb)
        self._tab_puerta(nb)
        self._tab_rechazados(nb)
        self._tab_base(nb)
        nb.bind("<<NotebookTabChanged>>", lambda e: self._al_cambiar(nb))
        self.actualizar_resumen()

    # ---------- utilidades ----------
    def bg(self, fn, ok=None, msg="Trabajando…"):
        """Ejecuta `fn` en un hilo para que la ventana no se congele."""
        self.status.set(msg)

        def trabajo():
            try:
                with self.lock:
                    r = fn()
            except Exception as e:
                self.root.after(0, lambda e=e: self._fallo(e))
                return
            self.root.after(0, lambda: (self.status.set("Listo"), ok(r) if ok else None))

        threading.Thread(target=trabajo, daemon=True).start()

    def _fallo(self, e):
        self.status.set("Error")
        messagebox.showerror("Error", str(e))

    def log(self, texto):
        self.txt_log.insert("end", f"[{datetime.now():%H:%M:%S}] {texto}\n")
        self.txt_log.see("end")

    def _al_cambiar(self, nb):
        t = nb.tab(nb.select(), "text")
        if t == "Revisión manual":
            self.cargar_pendientes()
        elif t == "Rechazados":
            self.cargar_rechazados()
        elif t == "Base de QRs":
            self.cargar_base()
        elif t == "Puerta":
            self.ent_qr.focus_set()

    # ---------- 1. Procesar ----------
    def _tab_procesar(self, nb):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="Procesar")
        self.lbl_resumen = ttk.Label(f, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_resumen.pack(anchor="w")
        fila = ttk.Frame(f)
        fila.pack(fill="x", pady=10)
        ttk.Button(fila, text="▶ Procesar recibos pendientes", command=self.procesar).pack(side="left")
        ttk.Button(fila, text="↻ Actualizar resumen", command=self.actualizar_resumen).pack(side="left", padx=8)
        self.txt_log = tk.Text(f, height=20, state="normal", font=("Consolas", 10))
        self.txt_log.pack(fill="both", expand=True)

    def actualizar_resumen(self):
        self.bg(self.mng.manual.resumen, lambda r: self.lbl_resumen.config(text=r), "Consultando…")

    def procesar(self):
        def ok(r):
            self.log(r["mensaje"])
            for m in r["mensajes"]:
                self.log("  · " + m)
            if r.get("detalle"):
                self.log("  ⚠ " + r["detalle"])
            self.actualizar_resumen()
        self.bg(self.mng.procesar_pendientes, ok, "Procesando recibos…")

    # ---------- 2. Revisión manual ----------
    def _tab_revision(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Revisión manual")
        izq = ttk.LabelFrame(f, text="Recibos en revisión", padding=6)
        izq.pack(side="left", fill="both", expand=True)
        m, self.t_pend = crear_tabla(izq, [("id", "Recibo", 60), ("nombre", "A nombre de", 220),
                                           ("motivo", "Motivo", 60)], 18)
        m.pack(fill="both", expand=True)
        self.t_pend.bind("<<TreeviewSelect>>", lambda e: self.mostrar_candidatos())
        ttk.Button(izq, text="↻ Recargar", command=self.cargar_pendientes).pack(anchor="w", pady=(6, 0))

        der = ttk.LabelFrame(f, text="Candidatos", padding=6)
        der.pack(side="left", fill="both", expand=True, padx=(10, 0))
        m, self.t_cand = crear_tabla(der, [("carnet", "Carnet", 90), ("nombre", "Nombre", 230),
                                           ("pct", "%", 50), ("est", "Estado", 80)], 12)
        m.pack(fill="both", expand=True)

        b = ttk.Frame(der)
        b.pack(fill="x", pady=6)
        self.v_buscar = tk.StringVar()
        e = ttk.Entry(b, textvariable=self.v_buscar)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.buscar())
        ttk.Button(b, text="Buscar", command=self.buscar).pack(side="left", padx=4)

        b2 = ttk.Frame(der)
        b2.pack(fill="x")
        self.v_carnet = tk.StringVar()
        ttk.Entry(b2, textvariable=self.v_carnet, width=14).pack(side="left")
        ttk.Button(b2, text="Aceptar por carnet", command=self.aceptar_carnet).pack(side="left", padx=4)

        b3 = ttk.Frame(der)
        b3.pack(fill="x", pady=(10, 0))
        ttk.Button(b3, text="✔ Aceptar seleccionado", command=self.aceptar_sel).pack(side="left")
        ttk.Button(b3, text="✖ Rechazar recibo", command=self.rechazar).pack(side="left", padx=8)

    def cargar_pendientes(self):
        def ok(lista):
            self.pend = lista
            vaciar(self.t_pend)
            vaciar(self.t_cand)
            for f in lista:
                self.t_pend.insert("", "end", iid=str(f["id_pago"]),
                                   values=(f["id_pago"], f["nombre"], f["motivo"]))
        self.bg(self.mng.manual.facturas_pendientes, ok, "Cargando recibos en revisión…")

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
        for i, c in enumerate(f["candidatos"]):
            self.t_cand.insert("", "end", iid=str(i), values=(
                c["carnet"], c["nombre_completo"], c["puntaje"],
                "YA VALIDADO" if c.get("ya_validado") else "Disponible"))

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
        texto = self.v_buscar.get().strip()
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
        self.actualizar_resumen()

    def aceptar_sel(self):
        f = self._factura_sel()
        c = self._cand_sel(f) if f else None
        if c and messagebox.askyesno("Confirmar", f"¿Aceptar el recibo #{f['id_pago']} para\n"
                                                  f"{c['nombre_completo']} ({c['carnet']})?"):
            self.bg(lambda: self.mng.manual.aceptar(f["id_pago"], c["carnet"]), self._tras_decision)

    def aceptar_carnet(self):
        f = self._factura_sel()
        carnet = self.v_carnet.get().strip()
        if f and carnet and messagebox.askyesno("Confirmar", f"¿Aceptar el recibo #{f['id_pago']} para el carnet {carnet}?"):
            self.bg(lambda: self.mng.manual.aceptar(f["id_pago"], carnet), self._tras_decision)

    def rechazar(self):
        f = self._factura_sel()
        if not f:
            return
        hay = any(not c.get("ya_validado") for c in f["candidatos"])
        motivo = "NM" if hay else "NC"
        if messagebox.askyesno("Confirmar", f"¿Rechazar el recibo #{f['id_pago']}? (motivo {motivo})"):
            self.bg(lambda: self.mng.manual.rechazar(f["id_pago"], motivo), self._tras_decision)

    # ---------- 3. Emitir QRs ----------
    def _tab_emitir(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Emitir QRs")
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Button(b, text="⚙ Emitir QRs de los aceptados", command=self.emitir).pack(side="left")
        ttk.Button(b, text="💾 Exportar CSV", command=self.exportar).pack(side="left", padx=8)
        ttk.Button(b, text="✔ Marcar seleccionado como enviado", command=self.marcar_enviado).pack(side="left")
        self.lbl_emitir = ttk.Label(f, text="Las cadenas solo existen en esta pantalla: expórtalas antes de cerrar.",
                                    foreground=ROJO)
        self.lbl_emitir.pack(anchor="w", pady=6)
        m, self.t_emit = crear_tabla(f, [("carnet", "Carnet", 90), ("nombre", "Nombre", 250),
                                         ("correo", "Correo", 230), ("cadena", "Cadena del QR", 380)], 18)
        m.pack(fill="both", expand=True)

    def emitir(self):
        def ok(r):
            self.listos = r["listos"]
            vaciar(self.t_emit)
            for q in self.listos:
                self.t_emit.insert("", "end", iid=q["carnet"],
                                   values=(q["carnet"], q["nombre"], q["correo"], q["cadena"]))
            msg = r["mensaje"]
            if r["fallidos"]:
                msg += "\nFallidos: " + "; ".join(f"{c} ({m})" for c, m in r["fallidos"])
            self.log(r["mensaje"])
            messagebox.showinfo("Emisión", msg)
        self.bg(self.mng.emitir_qrs, ok, "Emitiendo QRs…")

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
        if not sel:
            return
        self.bg(lambda: self.mng.confirmar_envio(sel[0]),
                lambda _: (self.t_emit.delete(sel[0]), self.log(f"Carnet {sel[0]} marcado como enviado")))

    # ---------- 4. Puerta ----------
    def _tab_puerta(self, nb):
        f = ttk.Frame(nb, padding=14)
        nb.add(f, text="Puerta")
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Día / sesión:").pack(side="left")
        self.v_ses = tk.StringVar(value="1")
        ttk.Combobox(top, textvariable=self.v_ses, state="readonly", width=4,
                     values=[str(i) for i in range(1, SESIONES + 1)]).pack(side="left", padx=6)
        ttk.Label(top, text="Escanea o pega el QR y presiona Enter:").pack(side="left", padx=(20, 6))
        self.ent_qr = ttk.Entry(top, font=("Consolas", 12))
        self.ent_qr.pack(side="left", fill="x", expand=True)
        self.ent_qr.bind("<Return>", lambda e: self.validar())

        self.lbl_res = tk.Label(f, text="ESPERANDO QR", bg=GRIS, fg="white", font=("Segoe UI", 28, "bold"),
                                height=3, wraplength=900)
        self.lbl_res.pack(fill="x", pady=14)
        m, self.t_hist = crear_tabla(f, [("hora", "Hora", 80), ("sesion", "Sesión", 60), ("carnet", "Carnet", 100),
                                         ("res", "Resultado", 420), ("afd", "Traza AFD", 80)], 10)
        m.pack(fill="both", expand=True)

    def validar(self):
        cadena = self.ent_qr.get().strip()
        self.ent_qr.delete(0, "end")
        if not cadena:
            return
        ses = int(self.v_ses.get())
        r = self.validador.validar(cadena, ses)
        ok = r["autorizado"]
        self.lbl_res.config(text=("✔ " if ok else "✖ ") + r["mensaje"], bg=VERDE if ok else ROJO)
        self.t_hist.insert("", 0, values=(f"{datetime.now():%H:%M:%S}", ses, r["carnet"] or "—",
                                           r["mensaje"], r["entrada"]))
        self.ent_qr.focus_set()

    # ---------- 5. Rechazados ----------
    def _tab_rechazados(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Rechazados")
        b = ttk.Frame(f)
        b.pack(fill="x")
        ttk.Label(b, text="Motivo:").pack(side="left")
        self.v_mot = tk.StringVar(value="Todos")
        cb = ttk.Combobox(b, textvariable=self.v_mot, state="readonly", width=8,
                          values=["Todos", "MONTO", "NC", "NM"])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.cargar_rechazados())
        ttk.Button(b, text="↻ Recargar", command=self.cargar_rechazados).pack(side="left")
        m, self.t_rech = crear_tabla(f, [("id", "Recibo", 60), ("no", "No. recibo", 100), ("nombre", "Pagador", 220),
                                         ("monto", "Monto", 70), ("mot", "Motivo", 70), ("fecha", "Fecha", 150)], 9)
        m.pack(fill="both", expand=True, pady=6)
        self.t_rech.bind("<<TreeviewSelect>>", lambda e: self.detalle_rechazo())
        self.txt_rech = tk.Text(f, height=8, font=("Consolas", 10))
        self.txt_rech.pack(fill="x")

    def cargar_rechazados(self):
        motivo = None if self.v_mot.get() == "Todos" else self.v_mot.get()

        def ok(filas):
            self.rechazados = filas
            vaciar(self.t_rech)
            for i, r in enumerate(filas):
                self.t_rech.insert("", "end", iid=str(i), values=(
                    r["id_pago"], r["no_recibo"], r["nombre_pagador"], r["monto"], r["motivo"], r["fecha_rechazo"]))
        self.bg(lambda: self.mng.manual.rechazados(motivo), ok, "Cargando rechazados…")

    def detalle_rechazo(self):
        sel = self.t_rech.selection()
        self.txt_rech.delete("1.0", "end")
        if not sel:
            return
        r = self.rechazados[int(sel[0])]
        self.txt_rech.insert("end", f"Candidatos probables para «{r['nombre_pagador']}»:\n")
        for c in r["candidatos"]:
            marca = "  [YA VINCULADO A OTRO RECIBO]" if c.get("ya_vinculado") else ""
            self.txt_rech.insert("end", f"  {c['carnet']:<12} {c['nombre_completo']:<40} {c['puntaje']}%{marca}\n")

    # ---------- 6. Base de QRs ----------
    def _tab_base(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Base de QRs")
        ttk.Button(f, text="↻ Recargar", command=self.cargar_base).pack(anchor="w")
        cols = [("carnet", "Carnet", 100), ("hash", "Hash (SHA-256)", 380), ("env", "Enviado", 70),
                ("fecha", "Emisión", 150)] + [(f"estado{i}", f"Día {i}", 60) for i in range(1, SESIONES + 1)]
        m, self.t_base = crear_tabla(f, cols, 20)
        m.pack(fill="both", expand=True, pady=6)

    def cargar_base(self):
        def ok(filas):
            vaciar(self.t_base)
            for r in filas:
                vals = [r["carnet"], r["codigo_hash"], "Sí" if r["enviado"] else "No", r["fecha_emision"]]
                vals += ["✔" if r.get(f"estado{i}") else "—" for i in range(1, SESIONES + 1)]
                self.t_base.insert("", "end", values=vals)
        self.bg(self.mng.obtener_base_qr, ok, "Cargando base de QRs…")


if __name__ == "__main__":
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()
