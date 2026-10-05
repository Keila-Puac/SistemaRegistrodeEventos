"""
    VALORES DE ENTRADA:
    1. Base de datos con los datos de factura
    2. Bases de datos con los datos de clientes
    3. Cantidad de sesiones para el evento
    4. Clave secreta para la creación de QR (opcional, si no se da, se genera una aleatoria)

    OPERACIONES INTERMEDIAS:
    1. Se toma un registro de factura
    2. Se busca, con fuzzy matching, los clientes que tengan un nombre similar
        2.1 Si tiene coincidencia alta (>90%), se hace el proceso de creación de QR
        2.2 Si tiene coincidencia media (80% - 90%) o hay varias coincidencias con un valor de coincidencia alto, se manda a revisión manual
        2.3 Si no tiene coincidencia, se manda a revisión manual
        DATO: los que se vayan a revisión manual se guardarán en una base de datos temporal para ser registrados uno por uno, y los validados a una base de datos aparte para confirmación de emisión de QR
    3.  Se muestran los resultados de la búsqueda de coincidencias y se hace la validación de los datos
    4. Se hace la creación de QR y se devuelve una base de datos de QR, junto con una llave especial de acceso

    VALORES DE SALIDA:
    1. Base de datos con datos de QR
    2. La clave secreta para la creación del QR
"""
import hmac, hashlib
import secrets
class qrDbMng:
    def __init__(self, db_facturas = None, db_clientes = None, sesiones = 1, key = None):
        self.db_facturas = db_facturas # base de datos de facturas
        self.db_clientes = db_clientes # base de datos de clientes
        self.sesiones = sesiones # cantidad de 'subeventos' del evento principal
        self.afnd = AFND(key or secrets.token_bytes(32)) # autómata finito no determinista para la creación de QR

    def generate_qr(self, nombre, carne):
        nombre = nombre.lower().strip().split(' ')
        data = f"{''.join(nombre)}:{carne}".encode()
        qr_hash = hmac.new(self.key, data, self.hasher).hexdigest()
        return qr_hash



class AFND:
    def __init__(self, key):
        self.estados = set()
        self.actual = None
        self.key = key
        self.hasher = hashlib.sha256()
        self.qr_db = []

    