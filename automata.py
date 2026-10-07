"""
SISTEMA DE EMISIÓN DE QRs PARA EL SIMPOSIO (AFND + revisión manual + persistencia)

VALORES DE ENTRADA:
    1. Tabla `pagos` (facturas) con el nombre del propietario del recibo
    2. Tabla `estudiantes` (clientes)
    3. Cantidad de sesiones para el evento

OPERACIONES INTERMEDIAS (ver "Documentación AFND"):
    q0 espera recibo -> q1 -> q2 (nombre) -> q3/q4 (fuzzy contra cada usuario)
    q4.1 / q4.1f descarta a quien ya fue validado, q4.2 calcula la similitud
    q5.1 (>95% único)          -> q7 aceptación directa
    q5.2 (varios altos)        -> q6 revisión manual
    q5.3 (nada >85%)           -> q6 revisión manual
    q5.4 (entre 85% y 95%)     -> q6 revisión manual
    q6 -> q7 (aceptado) o qE (rechazado: NC / NM)
    q8..q12 (emisión): cadena del QR, lista de booleanos por sesión, "leído",
                       guardado en la tabla externa de QRs y retorno de la base.

PROGRESO:
    - La base de datos MySQL es la fuente de verdad (pagos, pagos_pendientes,
      usuarios_aceptados). Cada escritura es atómica e idempotente.
    - progreso_qr.json guarda la bitácora (qué se procesó y cómo, rechazados).
    - cache_estudiantes.json permite arrancar aunque la BD no responda.
    - qr_externo.db (SQLite) es la tabla EXTERNA con los hashes de los QRs.
    - El envío de correos NO está aquí: se conecta con qrDbMng(enviador=...) o usando
      el retorno de emitir_qrs() y luego confirmar_envio(carnet).

VALORES DE SALIDA:
    1. Base de datos con datos de QR (solo hashes SHA-256, nunca el código original)
"""
import argparse
import contextlib
import json
import os
import secrets
import hashlib
import sqlite3
import time
import unicodedata
from datetime import datetime

from rapidfuzz import process, fuzz

from database import obtener_conexion, consultar_estudiantes

try:
    from mysql.connector.errors import OperationalError, InterfaceError
    ERRORES_RED = (OperationalError, InterfaceError, OSError)
except ImportError:                                   # pragma: no cover
    ERRORES_RED = (OSError,)

# ==========================================
# CONFIGURACIÓN  (ajusta estos nombres a tu esquema real)
# ==========================================
UMBRAL_ALTO = 95            # > 95%  -> coincidencia alta (docx: q5.1)
UMBRAL_MIN = 85             # < 85%  -> no hay coincidencia aceptable (docx: q5.3)
LIMITE_CANDIDATOS = 7

COL_NOMBRE_PAGO = "nombre_pagador"       # columna de `pagos` con el nombre del recibo
COL_CORREO = "correo"                    # columna de `estudiantes` con el email
ESTADO_PAGO_PENDIENTE = "PENDIENTE"      # estado de un pago sin procesar               (SUPUESTO)
ESTADO_PAGO_VALIDADO = "VALIDADO"
MONTO_CORRECTO = 300

ARCHIVO_PROGRESO = "progreso_qr.json"
ARCHIVO_CACHE = "cache_estudiantes.json"
DB_EXTERNA = "qr_externo.db"


# ==========================================
# ERRORES
# ==========================================
class ConexionPerdida(Exception):
    """La BD no respondió tras varios reintentos. El progreso ya está guardado."""


class YaAceptado(Exception):
    """Ese estudiante ya fue aceptado con otro pago."""


# ==========================================
# UTILIDADES
# ==========================================
def normalizar(texto):
    """Minúsculas, sin tildes y sin espacios de más."""
    texto = unicodedata.normalize("NFD", str(texto).lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(texto.split())


def iniciales(nombre):
    partes = normalizar(nombre).split()
    return "".join(p[0] for p in partes[:2]).upper()


def _extraer(entrada):
    """processor de rapidfuzz: acepta tanto la consulta (str) como el estudiante (dict)."""
    if isinstance(entrada, dict):
        entrada = entrada["nombre_completo"]
    return normalizar(entrada)


def con_bd(operacion, reintentos=3, espera=2.0):
    """
    Ejecuta `operacion(cursor)` en una transacción con reintentos ante desconexiones.
    La operación debe ser idempotente. Hace commit solo si todo salió bien.
    """
    ultimo = None
    for intento in range(1, reintentos + 1):
        db = None
        try:
            db = obtener_conexion()
            cur = db.cursor(dictionary=True)
            try:
                resultado = operacion(cur)
                db.commit()
            finally:
                cur.close()
            return resultado
        except ERRORES_RED as e:
            ultimo = e
            if db is not None:
                with contextlib.suppress(Exception):
                    db.rollback()
            if intento < reintentos:
                time.sleep(espera * intento)
        finally:
            if db is not None:
                with contextlib.suppress(Exception):
                    db.close()
    raise ConexionPerdida(f"Sin conexión a la base de datos tras {reintentos} intentos: {ultimo}")


def _fetch(cur, sql, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


# ==========================================
# PROGRESO EN DISCO
# ==========================================
class Progreso:
    """Bitácora en JSON, escrita de forma atómica (archivo temporal + os.replace)."""

    def __init__(self, ruta=ARCHIVO_PROGRESO):
        self.ruta = ruta
        self.datos = self._cargar()

    @staticmethod
    def _vacio():
        return {"version": 1, "procesados": {}, "rechazados": {}, "actualizado": None}

    def _cargar(self):
        if not os.path.exists(self.ruta):
            return self._vacio()
        try:
            with open(self.ruta, encoding="utf-8") as f:
                datos = json.load(f)
            base = self._vacio()
            base.update(datos)
            return base
        except (json.JSONDecodeError, OSError):
            # Archivo dañado (p. ej. corte de luz): se aparta y se sigue; la BD manda.
            with contextlib.suppress(OSError):
                os.replace(self.ruta, self.ruta + ".corrupto")
            return self._vacio()

    def guardar(self):
        self.datos["actualizado"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.ruta + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.ruta)

    def registrar(self, id_pago, resultado, carnet=None, traza=None):
        self.datos["procesados"][str(id_pago)] = {
            "resultado": resultado, "carnet": carnet, "traza": traza or [],
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }

    def rechazar(self, id_pago, motivo):
        self.datos["rechazados"][str(id_pago)] = motivo

    def esta_rechazado(self, id_pago):
        return str(id_pago) in self.datos["rechazados"]


# ==========================================
# AUTÓMATA
# ==========================================
class Automata:
    """
    AFND definido por la documentación. `actuales` es el conjunto de estados activos.
    Símbolos: E espera, R recibo, N nombre, C candidatos/comparación, S1..S4 resultado,
              M evaluación manual, V válido, X error (NC / NM).
    """
    NOMBRES = {
        "q0": "Esperando recibo de tesorería", "q1": "Recibo recibido",
        "q2": "Obteniendo nombre del propietario", "q3": "Buscando coincidencias en la BD",
        "q4": "Comparando similitud con cada usuario", "q4.1": "Verificando que no haya sido aceptado",
        "q4.1f": "El usuario ya fue validado", "q4.2": "Similitud por fuzzy comparison",
        "q5.1": "RES 1: valor único >95%", "q5.2": "RES 2: varias coincidencias altas",
        "q5.3": "RES 3: ninguna >85%", "q5.4": "RES 4: intermedio 85%-95%",
        "q6": "Evaluación manual", "q7": "ACEPTACIÓN DE USUARIO",
        "q8": "Se crea la cadena del QR", "q9": "Lista de booleanos por subevento",
        "q10": "Usuario establecido como leído", "q11": "Se guarda en el listado de QRs",
        "q12": "Se retorna la base de datos de QRs", "qE": "Error / rechazado",
    }
    DELTA = {
        ("q0", "E"): {"q0"}, ("q0", "R"): {"q1"},
        ("q1", "N"): {"q2"}, ("q2", "C"): {"q3"}, ("q3", "C"): {"q4"},
        ("q4", "C"): {"q4.1"},
        ("q4.1", "V"): {"q4.1f"}, ("q4.1", "C"): {"q4.2"},
        ("q4.1f", "C"): {"q4"}, ("q4.2", "C"): {"q4"},
        ("q4", "S1"): {"q5.1"}, ("q4", "S2"): {"q5.2"},
        ("q4", "S3"): {"q5.3"}, ("q4", "S4"): {"q5.4"},
        ("q5.1", "V"): {"q7"},
        ("q5.2", "M"): {"q6"}, ("q5.3", "M"): {"q6"}, ("q5.4", "M"): {"q6"},
        ("q6", "V"): {"q7"}, ("q6", "X"): {"qE"},
        ("q7", "V"): {"q8"}, ("q8", "V"): {"q9"}, ("q9", "V"): {"q10"},
        ("q10", "V"): {"q11"}, ("q11", "V"): {"q12"}, ("q12", "E"): {"q0"},
        ("q1", "N"): {"q2"}, ("q1", "X"): {"qE"},
    }
    INICIAL = "q0"
    FINALES = {"q7"}

    def __init__(self, inicio=None):
        self.actuales = {inicio or self.INICIAL}
        self.traza = [sorted(self.actuales)[0]]

    def leer(self, simbolo):
        siguientes = set()
        for q in self.actuales:
            siguientes |= self.DELTA.get((q, simbolo), set())
        if not siguientes:
            raise ValueError(f"Sin transición desde {sorted(self.actuales)} con '{simbolo}'")
        self.actuales = siguientes
        self.traza += [simbolo, sorted(siguientes)[0]]
        return siguientes

    def acepta(self):
        return bool(self.actuales & self.FINALES)

    def reiniciar(self):
        self.__init__()


class AFND(Automata):
    """Autómata + acceso a datos para evaluar un recibo contra los estudiantes."""

    def __init__(self, inicio=None):
        super().__init__(inicio)
        self._est_list = None

    # ---------- estudiantes (con caché para trabajar sin conexión) ----------
    @property
    def est_list(self):
        if self._est_list is None:
            self._est_list = self.cargar_estudiantes()
        return self._est_list

    def cargar_estudiantes(self):
        try:
            estudiantes = consultar_estudiantes()
            with open(ARCHIVO_CACHE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(estudiantes, f, ensure_ascii=False, default=str)
            os.replace(ARCHIVO_CACHE + ".tmp", ARCHIVO_CACHE)
            return estudiantes
        except ERRORES_RED:
            if os.path.exists(ARCHIVO_CACHE):
                print("⚠ Sin conexión: usando la copia local de estudiantes.")
                with open(ARCHIVO_CACHE, encoding="utf-8") as f:
                    return json.load(f)
            raise ConexionPerdida("Sin conexión y sin copia local de estudiantes.")

    # ---------- consultas ----------
    def carnets_aceptados(self):
        filas = con_bd(lambda c: _fetch(c, "SELECT carnet FROM usuarios_aceptados"))
        return [str(f["carnet"]) for f in filas]

    # alias con el nombre que usabas
    obtener_leidos = carnets_aceptados

    def obtener_pendientes(self):
        aceptados = set(self.carnets_aceptados())
        return [e for e in self.est_list if str(e["carnet"]) not in aceptados]

    def obtener_facturas_por_procesar(self, progreso=None):
        """Pagos pendientes que aún no están en revisión manual ni fueron rechazados."""
        sql = (f"SELECT id_pago, monto, {COL_NOMBRE_PAGO} AS nombre FROM pagos "
               "WHERE estado_pago = %s AND id_pago NOT IN (SELECT id_pago FROM pagos_pendientes)")
        filas = con_bd(lambda c: _fetch(c, sql, (ESTADO_PAGO_PENDIENTE,)))
        if progreso:
            filas = [f for f in filas if not progreso.esta_rechazado(f["id_pago"])]
        return filas

    # ---------- fuzzy ----------
    def obtener_similares(self, nombre, lista=None, limite=LIMITE_CANDIDATOS, umbral=UMBRAL_MIN):
        lista = self.obtener_pendientes() if lista is None else lista
        if not nombre or not lista:
            return []
        resultados = process.extract(nombre, lista, scorer=fuzz.WRatio, processor=_extraer,
                                     limit=limite, score_cutoff=umbral)
        return [{"carnet": str(est["carnet"]), "nombre_completo": est["nombre_completo"],
                 "puntaje": round(float(p), 1)} for est, p, _ in resultados]

    @staticmethod
    def clasificar(candidatos):
        """Devuelve S1..S4 según la documentación."""
        if not candidatos:
            return "S3"
        mejor = candidatos[0]["puntaje"]
        if mejor <= UMBRAL_ALTO:
            return "S4"                                    # intermedio
        if len(candidatos) > 1 and candidatos[1]["puntaje"] > UMBRAL_ALTO:
            return "S2"                                    # varios altos
        return "S1"                                        # único y alto

    # ---------- flujo de un recibo ----------
    @staticmethod
    def _monto_valido(monto):
        try:
            return float(monto) == MONTO_CORRECTO
        except (TypeError, ValueError):
            return False
        
    def procesar_factura(self, factura):
        """Corre el autómata para un recibo. Devuelve dict con el resultado."""
        self.reiniciar()
        self.leer("R")
        if not self._monto_valido(factura.get("monto")):
            self.leer("X")
            return {"id_pago": factura["id_pago"], "simbolo": "X", "carnet": None,
                    "estado_final": "qE", "traza": self.traza,
                    "mensaje": f"Recibo #{factura['id_pago']} rechazado: monto {factura.get('monto')} "
                                f"distinto de {MONTO_CORRECTO}"}
        self.leer("N")
        nombre = factura.get("nombre") or ""
        self.leer("C")
        self.leer("C")                                     # q4

        aceptados = set(self.carnets_aceptados())
        todos = self.est_list
        ya = [e for e in todos if str(e["carnet"]) in aceptados]
        disponibles = [e for e in todos if str(e["carnet"]) not in aceptados]

        candidatos = self.obtener_similares(nombre, disponibles)
        ya_validados = [dict(c, ya_validado=True) for c in
                        self.obtener_similares(nombre, ya, limite=3, umbral=UMBRAL_ALTO)]

        for _ in ya_validados:                             # q4 -> q4.1 -> q4.1f -> q4
            self.leer("C"); self.leer("V"); self.leer("C")
        for _ in candidatos:                               # q4 -> q4.1 -> q4.2 -> q4
            self.leer("C"); self.leer("C"); self.leer("C")

        simbolo = self.clasificar(candidatos)
        self.leer(simbolo)
        resultado = {"id_pago": factura["id_pago"], "simbolo": simbolo, "carnet": None}

        if simbolo == "S1":
            self.leer("V")                                 # q7
            resultado["carnet"] = candidatos[0]["carnet"]
            self.establecer_aceptado(resultado["carnet"], factura["id_pago"])
        else:
            self.leer("M")                                 # q6
            self.a_revision_manual(candidatos + ya_validados, factura["id_pago"], simbolo)

        resultado["estado_final"] = sorted(self.actuales)[0]
        resultado["traza"] = self.traza
        if simbolo == "S1":
            resultado["mensaje"] = (f"Recibo #{factura['id_pago']} aceptado: "
                                    f"{candidatos[0]['nombre_completo']} ({resultado['carnet']}, "
                                    f"{candidatos[0]['puntaje']}%)")
        else:
            motivos = {"S2": "varias coincidencias altas", "S3": "sin coincidencias aceptables",
                       "S4": "coincidencia intermedia"}
            resultado["mensaje"] = f"Recibo #{factura['id_pago']} enviado a revisión manual: {motivos[simbolo]}"
        return resultado

    # ---------- escrituras (atómicas e idempotentes) ----------
    def establecer_aceptado(self, carnet, id_pago):
        carnet = str(carnet)

        def op(c):
            c.execute("SELECT carnet FROM usuarios_aceptados WHERE carnet = %s", (carnet,))
            existe = c.fetchone() is not None
            c.execute("SELECT estado_pago FROM pagos WHERE id_pago = %s", (id_pago,))
            pago = c.fetchone()
            if existe:
                if pago and pago["estado_pago"] == ESTADO_PAGO_VALIDADO:
                    return "YA_REGISTRADO"                 # reintento tras un corte
                raise YaAceptado(f"El carnet {carnet} ya fue aceptado con otro pago.")
            c.execute("INSERT INTO usuarios_aceptados (carnet) VALUES (%s)", (carnet,))
            c.execute("UPDATE pagos SET estado_pago = %s WHERE id_pago = %s",
                      (ESTADO_PAGO_VALIDADO, id_pago))
            c.execute("DELETE FROM pagos_pendientes WHERE id_pago = %s", (id_pago,))
            return "OK"

        return con_bd(op)

    def a_revision_manual(self, candidatos, id_pago, motivo):
        relacionados = json.dumps({"motivo": motivo, "candidatos": candidatos}, ensure_ascii=False)

        def op(c):
            c.execute("SELECT id_pago FROM pagos_pendientes WHERE id_pago = %s", (id_pago,))
            if c.fetchone() is None:
                c.execute("INSERT INTO pagos_pendientes (id_pago, relacionados) VALUES (%s, %s)",
                          (id_pago, relacionados))

        con_bd(op)


# ==========================================
# REVISIÓN MANUAL
# ==========================================
class manualCheckout:
    """Evalúa los recibos que el autómata mandó a q6 y consulta estudiantes sin aceptar."""

    def __init__(self, afnd, progreso):
        self.afnd = afnd
        self.progreso = progreso

    def facturas_pendientes(self):
        sql = (f"SELECT pp.id_pago, pp.relacionados, p.{COL_NOMBRE_PAGO} AS nombre "
               "FROM pagos_pendientes pp LEFT JOIN pagos p ON p.id_pago = pp.id_pago")
        filas = con_bd(lambda c: _fetch(c, sql))
        salida = []
        for f in filas:
            if self.progreso.esta_rechazado(f["id_pago"]):
                with contextlib.suppress(ConexionPerdida):   # limpieza de un corte previo
                    con_bd(lambda c, i=f["id_pago"]: c.execute(
                        "DELETE FROM pagos_pendientes WHERE id_pago = %s", (i,)))
                continue
            try:
                rel = json.loads(f["relacionados"])
            except (TypeError, ValueError):
                rel = {"motivo": "?", "candidatos": []}
            salida.append({"id_pago": f["id_pago"], "nombre": f["nombre"],
                           "motivo": rel.get("motivo"), "candidatos": rel.get("candidatos", [])})
        return salida

    def estudiantes_sin_aceptar(self):
        return self.afnd.obtener_pendientes()

    def buscar(self, texto, limite=10):
        return self.afnd.obtener_similares(texto, limite=limite, umbral=50)

    def aceptar(self, id_pago, carnet):
        carnet = str(carnet)
        if carnet not in {str(e["carnet"]) for e in self.afnd.est_list}:
            raise ValueError(f"El carnet {carnet} no existe en estudiantes.")
        if carnet in set(self.afnd.carnets_aceptados()):
            raise YaAceptado(f"El carnet {carnet} ya fue aceptado.")
        self.afnd.establecer_aceptado(carnet, id_pago)
        self.progreso.registrar(id_pago, "MANUAL_V", carnet, ["q6", "V", "q7"])
        self.progreso.guardar()
        return {"ok": True, "mensaje": f"Recibo #{id_pago} aceptado manualmente para el carnet {carnet}"}

    def rechazar(self, id_pago, motivo="NM"):
        """motivo: NC (no hay nombres relacionados) o NM (se rechazaron los sugeridos)."""
        if motivo not in ("NC", "NM"):
            raise ValueError("motivo debe ser 'NC' o 'NM'")
        self.progreso.rechazar(id_pago, motivo)            # primero el progreso...
        self.progreso.registrar(id_pago, f"MANUAL_X_{motivo}", None, ["q6", "X", "qE"])
        self.progreso.guardar()
        con_bd(lambda c: c.execute("DELETE FROM pagos_pendientes WHERE id_pago = %s", (id_pago,)))
        causa = "sin nombres relacionados" if motivo == "NC" else "se rechazaron los nombres sugeridos"
        return {"ok": True, "mensaje": f"Recibo #{id_pago} rechazado ({motivo}: {causa})"}

    def resumen(self):
        pend = self.facturas_pendientes()
        return (f"Recibos en revisión: {len(pend)} | "
                f"Estudiantes sin aceptar: {len(self.estudiantes_sin_aceptar())}")

    @staticmethod
    def _mostrar(f, salida):
        salida(f"\n── Recibo #{f['id_pago']} · a nombre de: {f['nombre']!r} · motivo: {f['motivo']}")
        if not f["candidatos"]:
            salida("   (sin candidatos)")
        for i, c in enumerate(f["candidatos"], 1):
            marca = "  [YA VALIDADO]" if c.get("ya_validado") else ""
            salida(f"   {i}) {c['nombre_completo']}  ({c['carnet']})  {c['puntaje']}%{marca}")
        salida("   [número]=aceptar · b texto=buscar · c carnet=aceptar por carnet · "
               "r=rechazar · s=saltar · q=salir")

    def revisar_todo(self, entrada=input, salida=print):
        """Bucle interactivo de consola. Se puede salir con q y retomar después."""
        try:
            pendientes = self.facturas_pendientes()
            if not pendientes:
                salida("No hay recibos pendientes de revisión.")
                return
            for f in pendientes:
                while True:
                    self._mostrar(f, salida)
                    op = entrada("> ").strip()
                    bajo = op.lower()
                    try:
                        if bajo == "q":
                            salida("Progreso guardado. Puedes continuar luego.")
                            return
                        if bajo == "s":
                            break
                        if bajo == "r":
                            validos = [c for c in f["candidatos"] if not c.get("ya_validado")]
                            salida("   " + self.rechazar(f["id_pago"], "NM" if validos else "NC")["mensaje"])
                            break
                        if bajo.startswith("b "):
                            conocidos = {c["carnet"] for c in f["candidatos"]}
                            f["candidatos"] += [c for c in self.buscar(op[2:]) if c["carnet"] not in conocidos]
                            continue
                        if bajo.startswith("c "):
                            salida("   " + self.aceptar(f["id_pago"], op[2:].strip())["mensaje"])
                            break
                        if bajo.isdigit() and 1 <= int(bajo) <= len(f["candidatos"]):
                            cand = f["candidatos"][int(bajo) - 1]
                            if cand.get("ya_validado"):
                                salida("   Ese estudiante ya fue validado; no se puede aceptar de nuevo.")
                                continue
                            salida("   " + self.aceptar(f["id_pago"], cand["carnet"])["mensaje"])
                            break
                        salida("   Opción no válida.")
                    except (ValueError, YaAceptado) as e:
                        salida(f"   ✖ {e}")
        except ConexionPerdida as e:
            salida(f"Conexión perdida: {e}\nTu progreso está guardado; vuelve a ejecutar la revisión.")


# ==========================================
# GESTOR PRINCIPAL
# ==========================================
class qrDbMng:
    def __init__(self, sesiones=1, ruta_db=DB_EXTERNA, ruta_progreso=ARCHIVO_PROGRESO,
                 enviador=None):
        # enviador: función opcional  enviador(destino, nombre, carnet, cadena) -> True si se envió.
        # La implementa quien haga el envío de correos; sin ella, emitir_qrs() solo prepara los QRs.
        self.enviador = enviador
        self.sesiones = sesiones                  # cantidad de 'subeventos' del evento principal
        self.ruta_db = ruta_db
        self.progreso = Progreso(ruta_progreso)
        self.afnd = AFND()
        self.manual = manualCheckout(self.afnd, self.progreso)
        self.create_qr_db()

    # ---------- tabla externa (SQLite) ----------
    @contextlib.contextmanager
    def _ext(self):
        conn = sqlite3.connect(self.ruta_db)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create_qr_db(self):
        """Crea la tabla externa de QRs; si aumentan las sesiones, agrega las columnas faltantes."""
        with self._ext() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS qr_tickets (
                    id_codigo INTEGER PRIMARY KEY AUTOINCREMENT,
                    carnet TEXT NOT NULL UNIQUE,
                    codigo_hash TEXT NOT NULL UNIQUE,
                    enviado INTEGER NOT NULL DEFAULT 0,
                    fecha_emision TEXT
                )""")
            existentes = {f["name"] for f in db.execute("PRAGMA table_info(qr_tickets)")}
            for i in range(1, self.sesiones + 1):
                if f"estado{i}" not in existentes:
                    db.execute(f"ALTER TABLE qr_tickets ADD COLUMN estado{i} INTEGER NOT NULL DEFAULT 0")

    def obtener_base_qr(self):
        with self._ext() as db:
            return [dict(r) for r in db.execute("SELECT * FROM qr_tickets ORDER BY id_codigo")]

    # ---------- QR ----------
    def generar_cadena(self, estudiante):
        """q8: iniciales + carnet + parte aleatoria."""
        return iniciales(estudiante["nombre_completo"]) + str(estudiante["carnet"]) + secrets.token_hex(16)

    def hash_codigo(self, cadena):
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()

    def _guardar_qr(self, carnet, codigo_hash):
        """q11: guarda (o reemplaza, si aún no se había enviado) el hash del QR."""
        ahora = datetime.now().isoformat(timespec="seconds")
        with self._ext() as db:
            db.execute("""
                INSERT INTO qr_tickets (carnet, codigo_hash, enviado, fecha_emision)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(carnet) DO UPDATE SET codigo_hash = excluded.codigo_hash,
                                                 fecha_emision = excluded.fecha_emision
                WHERE qr_tickets.enviado = 0""", (carnet, codigo_hash, ahora))

    def _marcar_enviado(self, carnet):
        with self._ext() as db:
            db.execute("UPDATE qr_tickets SET enviado = 1 WHERE carnet = ?", (carnet,))

    def _carnets_enviados(self):
        with self._ext() as db:
            return {r["carnet"] for r in db.execute("SELECT carnet FROM qr_tickets WHERE enviado = 1")}

    # ---------- pasos del flujo ----------
    def procesar_pendientes(self, limite=None):
        """Pasa los recibos pendientes por el autómata. Se puede interrumpir y reanudar."""
        res = {"aceptados": 0, "a_revision": 0, "interrumpido": False, "mensajes": []}
        try:
            facturas = self.afnd.obtener_facturas_por_procesar(self.progreso)
            for f in facturas[:limite]:
                r = self.afnd.procesar_factura(f)
                if r["simbolo"] == "X":
                    self.progreso.rechazar(f["id_pago"], "MONTO")
                self.progreso.registrar(f["id_pago"], r["simbolo"], r["carnet"], r["traza"])
                self.progreso.guardar()
                clave = {"S1": "aceptados", "X": "rechazados"}.get(r["simbolo"], "a_revision")
                res[clave] += 1
                res["mensajes"].append(r["mensaje"])
        except ConexionPerdida as e:
            res["interrumpido"] = True
            res["detalle"] = str(e)
        res["mensaje"] = (f"Procesados: {res['aceptados']} aceptados, {res['a_revision']} a revisión manual, "
                          f"{res['rechazados']} rechazados por monto"
                          + (". Proceso interrumpido por pérdida de conexión; el progreso quedó guardado."
                             if res["interrumpido"] else "."))
        return res

    def emitir_qrs(self, carnets=None):
        """
        Q8–Q12. Para cada aceptado sin QR: crea la cadena, guarda su hash en la tabla externa
        y, si hay `enviador`, la envía. Devuelve:
            "listos"   : [{carnet, nombre, correo, cadena}]  QRs creados que falta enviar
            "enviados" : [carnet]                            ya enviados (si hay enviador)
            "fallidos" : [(carnet, motivo)]
            "mensaje"  : texto final para la interfaz
        `cadena` es el contenido del QR y solo existe en este retorno (no se guarda en ningún lado):
        quien envía debe usarla ya, y luego llamar a `confirmar_envio(carnet)`.
        `carnets` permite emitir solo un subconjunto. Los aceptados que no se emiten
        quedan "en espera" sin código.
        """
        aceptados = self.afnd.carnets_aceptados()
        enviados = self._carnets_enviados()
        solo = None if carnets is None else set(map(str, carnets))
        cola = [c for c in aceptados if c not in enviados and (solo is None or c in solo)]
        est_por_carnet = {str(e["carnet"]): e for e in self.afnd.est_list}
        res = {"listos": [], "enviados": [], "fallidos": []}

        for carnet in cola:
            est = est_por_carnet.get(carnet)
            if not est:
                res["fallidos"].append((carnet, "no existe en estudiantes"))
                continue
            auto = Automata("q7")
            auto.leer("V")                                  # q8: cadena
            cadena = self.generar_cadena(est)
            auto.leer("V")                                  # q9: booleanos por sesión (columnas estadoN = 0)
            auto.leer("V")                                  # q10: leído (ya está en usuarios_aceptados)
            auto.leer("V")                                  # q11: guardar el hash
            self._guardar_qr(carnet, self.hash_codigo(cadena))
            auto.leer("V")                                  # q12
            self.progreso.registrar(f"qr:{carnet}", "QR_CREADO", carnet, auto.traza)
            self.progreso.guardar()

            if self.enviador is None:
                res["listos"].append({"carnet": carnet, "nombre": est["nombre_completo"],
                                      "correo": est.get(COL_CORREO), "cadena": cadena})
                continue
            try:
                if self.enviador(est.get(COL_CORREO), est["nombre_completo"], carnet, cadena):
                    self.confirmar_envio(carnet)
                    res["enviados"].append(carnet)
                else:
                    res["fallidos"].append((carnet, "el envío no fue confirmado"))
            except Exception as e:                          # el enviador es código externo
                res["fallidos"].append((carnet, f"error de envío: {e}"))

        res["mensaje"] = (f"QRs creados pendientes de envío: {len(res['listos'])} · "
                          f"enviados: {len(res['enviados'])} · fallidos: {len(res['fallidos'])}")
        return res

    def confirmar_envio(self, carnet):
        """Marca un QR como enviado (lo llama quien envía los correos al terminar)."""
        self._marcar_enviado(str(carnet))
        self.progreso.registrar(f"qr:{carnet}", "ENVIADO", str(carnet), [])
        self.progreso.guardar()

    def verificar_qr(self, cadena, sesion=1):
        """Puerta del evento: valida el QR y marca la sesión de forma atómica."""
        if not 1 <= sesion <= self.sesiones:
            raise ValueError("sesión fuera de rango")
        h = self.hash_codigo(cadena)
        with self._ext() as db:
            fila = db.execute("SELECT carnet FROM qr_tickets WHERE codigo_hash = ?", (h,)).fetchone()
            if not fila:
                return {"autorizado": False, "mensaje": "QR INEXISTENTE"}
            cur = db.execute(f"UPDATE qr_tickets SET estado{sesion} = 1 "
                             f"WHERE codigo_hash = ? AND estado{sesion} = 0", (h,))
            if cur.rowcount == 0:
                return {"autorizado": False, "mensaje": "QR YA USADO EN ESTA SESIÓN"}
            return {"autorizado": True, "mensaje": "ACCESO AUTORIZADO", "carnet": fila["carnet"]}


# ==========================================
# LÍNEA DE COMANDOS:  python qr_sistema.py procesar | revisar | emitir | estado
# ==========================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("accion", choices=["procesar", "revisar", "emitir", "estado"])
    ap.add_argument("--sesiones", type=int, default=1)
    a = ap.parse_args()
    mng = qrDbMng(sesiones=a.sesiones)
    try:
        if a.accion == "procesar":
            print(mng.procesar_pendientes())
        elif a.accion == "revisar":
            mng.manual.revisar_todo()
        elif a.accion == "emitir":
            print(mng.emitir_qrs())
        else:
            print(mng.manual.resumen())
    except ConexionPerdida as e:
        print("Conexión perdida:", e, "\nEl progreso está guardado; vuelve a ejecutar el comando.")