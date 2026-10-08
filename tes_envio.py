from generador_qr_pdf import enviar_correo_twilo, generar_pdf_ticket

# 1. Datos de prueba
correo_destino = "correo_prueba@gamil.com"
nombre_prueba = "Usuario de Prueba"
carnet_prueba = "1234567"
cadena_qr_prueba = "TICKET-TEST-1234567-EVENTO"

# Datos para el PDF
estudiante_prueba = {
    "nombre_completo": nombre_prueba,
    "carnet": carnet_prueba,
    "carrera": "Ingeniería en Sistemas",
    "correo": correo_destino
}

ruta_pdf_test = f"Ticket_Test_{carnet_prueba}.pdf"

print("1. Generando PDF de prueba...")
generar_pdf_ticket(estudiante_prueba, cadena_qr_prueba, ruta_pdf_test)
print(f"PDF creado: {ruta_pdf_test}")

print("\n2. Enviando correo vía Twilio SendGrid...")
exito = enviar_correo_twilo(correo_destino, nombre_prueba, ruta_pdf_test)

if exito:
    print("\n¡Prueba exitosa! Revisa tu bandeja de entrada (y la carpeta de SPAM).")
else:
    print("\nEl envío falló. Revisa la clave API y el correo remitente.")