from datetime import datetime
import mysql.connector

# Configuración de conexión remota con Alwaysdata
DB_CONFIG = {
    'host': 'mysql-jack-vg.alwaysdata.net',
    'user': 'jack-vg',
    'password': '--',  # se pone al contraseña de la base  de datos, ahi me preguntan la contra x,d
    #no voy a subir eso a esata wea
    'database': 'jack-vg_simposio_db',
    'port': 3306
}


def obtener_conexion():
    """Establece conexión activa con la base de datos remota en Alwaysdata."""
    return mysql.connector.connect(**DB_CONFIG)


# ==========================================
# FUNCIONES
# ==========================================

def consultar_estudiantes():
    """Obtiene el listado completo de estudiantes registrados."""
    db = obtener_conexion()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM estudiantes")
    estudiantes = cursor.fetchall()
    cursor.close()
    db.close()
    return estudiantes


def obtener_ticket_disponible():
    """Busca el primer ticket que tenga estado 'DISPONIBLE'."""
    db = obtener_conexion()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tickets WHERE estado = 'DISPONIBLE' LIMIT 1")
    ticket = cursor.fetchone()
    cursor.close()
    db.close()
    return ticket


def vincular_pago_exitoso(carnet, id_pago, id_ticket):
    """
    Registra la validación oficial en la BD, pasa el pago a VALIDADO
    y asigna el ticket correspondiente.
    """
    db = obtener_conexion()
    cursor = db.cursor()

    # Crear registro de validación
    cursor.execute("""
        INSERT INTO validaciones (carnet, id_pago, id_ticket)
        VALUES (%s, %s, %s)
    """, (carnet, id_pago, id_ticket))

    # Actualizar estado del pago
    cursor.execute("UPDATE pagos SET estado_pago = 'VALIDADO' WHERE id_pago = %s", (id_pago,))

    # Actualizar estado del ticket
    cursor.execute("UPDATE tickets SET estado = 'ASIGNADO' WHERE id_ticket = %s", (id_ticket,))

    db.commit()
    cursor.close()
    db.close()


def validar_ingreso_qr(codigo_qr):
    """
    Función del escáner en puerta (AFD de control de acceso).
    Comprueba si el QR es válido, si ya fue usado o si autoriza el ingreso.
    """
    db = obtener_conexion()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT t.id_ticket, t.estado AS estado_ticket, v.id_validacion, e.nombre_completo, e.carnet
        FROM tickets t
        LEFT JOIN validaciones v ON t.id_ticket = v.id_ticket
        LEFT JOIN estudiantes e ON v.carnet = e.carnet
        WHERE t.codigo_qr = %s
    """
    cursor.execute(query, (codigo_qr,))
    resultado = cursor.fetchone()

    if not resultado:
        cursor.close()
        db.close()
        return {"autorizado": False, "mensaje": "TICKET INEXISTENTE"}

    if resultado["estado_ticket"] == "UTILIZADO":
        cursor.close()
        db.close()
        return {
            "autorizado": False,
            "mensaje": f"ACCESO DENEGADO: Ticket ya usado por {resultado['nombre_completo']}"
        }

    elif resultado["estado_ticket"] == "ASIGNADO":
        fecha_actual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Marcar como utilizado y registrar la hora de llegada
        cursor.execute("UPDATE tickets SET estado = 'UTILIZADO' WHERE id_ticket = %s", (resultado["id_ticket"],))
        cursor.execute("UPDATE validaciones SET fecha_ingreso_evento = %s WHERE id_validacion = %s",
                       (fecha_actual, resultado["id_validacion"]))
        db.commit()
        cursor.close()
        db.close()
        return {
            "autorizado": True,
            "mensaje": f"ACCESO AUTORIZADO: Bienvenido/a {resultado['nombre_completo']}",
            "carnet": resultado["carnet"]
        }

    else:
        cursor.close()
        db.close()
        return {"autorizado": False, "mensaje": "TICKET NO ASIGNADO A NINGÚN ESTUDIANTE"}


# ==========================================
# peuab de conexión, paver si jala la wea
# ==========================================
if __name__ == "__main__":
    try:
        estudiantes = consultar_estudiantes()
        print("Conexión exitosa a Alwaysdata. Estudiantes encontrados en BD:")
        if not estudiantes:
            print("  (Aún no hay estudiantes registrados en la tabla)")
        for est in estudiantes:
            print(f"  - {est['carnet']}: {est['nombre_completo']}")
    except Exception as e:
        print("Error al conectar con la base de datos:", e)