<?php
// Endpoint JSON de la versión móvil: valida un ticket y responde el resultado.
require_once 'includes/datos.php';
require_once 'includes/db.php';
header('Content-Type: application/json; charset=utf-8');
if (empty($_SESSION['personal'])) { http_response_code(401); echo json_encode(['ok' => false, 'titulo' => 'Sesión vencida', 'texto' => 'Vuelve a escribir el PIN.']); exit; }
$cod = trim($_POST['codigo'] ?? ''); $dia = (int)($_POST['dia'] ?? 1);
try { $r = $cod === '' ? ['err', 'Falta el código', 'Escanea el QR de nuevo.'] : validar_ingreso($cod, $dia); }
catch (Throwable $x) { $r = ['err', 'Sin conexión con la base', 'Reintenta en unos segundos.']; }
echo json_encode(['ok' => $r[0] === 'ok', 'titulo' => $r[1], 'texto' => $r[2], 'datos' => $r[3] ?? null]);
