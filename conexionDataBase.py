"""Compatibilidad con módulos antiguos: reutiliza la conexión central de database.py."""
from database import DB_CONFIG, obtener_conexion

if __name__ == "__main__":
    conexion = None
    try:
        conexion = obtener_conexion()
        print("Conexión exitosa a la base de datos.")
        cursor = conexion.cursor()
        cursor.execute("SHOW TABLES")
        print("Tablas disponibles:")
        for fila in cursor.fetchall():
            print(" -", fila[0])
        cursor.close()
    except Exception as error:
        print("No fue posible conectar. Revisa DB_HOST, DB_USER, DB_PASSWORD, DB_NAME y DB_PORT.")
        print("Detalle:", error)
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()
