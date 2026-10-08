<?php
// Port a PHP de las funciones de database.py (mismas tablas de Alwaysdata).
require_once __DIR__ . '/config.php';

function db() {
    static $pdo = null;
    if (!$pdo) {
        $c = DB_CFG;
        $pdo = new PDO("mysql:host={$c['host']};port={$c['port']};dbname={$c['database']};charset=utf8mb4",
            $c['user'], $c['password'],
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]);
    }
    return $pdo;
}
function uno($sql, $p = []) { $s = db()->prepare($sql); $s->execute($p); return $s->fetch() ?: null; }

function nombre_tokens($s) {
    $s = strtr($s, ['á'=>'a','é'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ü'=>'u','ñ'=>'n','Á'=>'a','É'=>'e','Í'=>'i','Ó'=>'o','Ú'=>'u','Ü'=>'u','Ñ'=>'n']);
    return array_values(array_filter(preg_split('/[^a-z]+/', strtolower($s))));
}
function nombres_compatibles($a, $b) {
    $a = nombre_tokens($a); $b = nombre_tokens($b);
    return $a && $b && (!array_diff($a, $b) || !array_diff($b, $a));
}

/** Asigna un ticket DISPONIBLE (equivale a obtener_ticket_disponible + vincular_pago_exitoso), de forma atómica. */
function asignar_ticket($carnet, $id_pago) {
    $db = db(); $db->beginTransaction();
    try {
        $db->prepare("SELECT id_pago FROM pagos WHERE id_pago=? FOR UPDATE")->execute([$id_pago]);
        if (uno("SELECT 1 AS x FROM validaciones WHERE id_pago=? OR carnet=?", [$id_pago, $carnet])) { $db->rollBack(); return 'dup'; }
        $t = uno("SELECT * FROM tickets WHERE estado='DISPONIBLE' ORDER BY id_ticket LIMIT 1 FOR UPDATE");
        if (!$t) { $db->rollBack(); return null; }
        $db->prepare("INSERT INTO validaciones (carnet,id_pago,id_ticket) VALUES (?,?,?)")->execute([$carnet, $id_pago, $t['id_ticket']]);
        $db->prepare("UPDATE pagos SET estado_pago='VALIDADO' WHERE id_pago=?")->execute([$id_pago]);
        $db->prepare("UPDATE tickets SET estado='ASIGNADO' WHERE id_ticket=?")->execute([$t['id_ticket']]);
        $db->commit(); return $t;
    } catch (Throwable $x) { $db->rollBack(); throw $x; }
}

/** Primer momento + segundo momento. Devuelve [estado, título, texto, ticket, estudiante]. */
function procesar_validacion($carnet, $recibo) {
    $est = uno("SELECT * FROM estudiantes WHERE carnet=?", [$carnet]);
    if (!$est) return ['err', 'No aparece en el listado oficial', 'Revisa tu carné. Si es correcto, pide a la Coordinación que te agregue.'];
    $pago = uno("SELECT * FROM pagos WHERE no_recibo=?", [$recibo]);
    if (!$pago) return ['err', 'Pago no localizado', 'No encontramos ese recibo en el reporte de Tesorería.'];
    if (!nombres_compatibles($pago['nombre_pagador'], $est['nombre_completo']))
        return ['warn', 'Enviado a revisión manual', 'El nombre del recibo no coincide con el del carné. La Coordinación lo revisará.'];

    $sel = "SELECT v.carnet, t.id_ticket, t.codigo_qr FROM validaciones v JOIN tickets t ON t.id_ticket=v.id_ticket WHERE ";
    $v = uno($sel . "v.id_pago=?", [$pago['id_pago']]);
    if ($v && (string)$v['carnet'] !== (string)$carnet)
        return ['err', 'Pago duplicado', 'Ese número de recibo ya fue usado por otro estudiante.'];
    if (!$v) $v = uno($sel . "v.carnet=?", [$carnet]);
    if ($v) return ['ok', 'Ticket ya asignado', 'Este es tu ticket. Presenta el QR en el ingreso.', $v, $est];

    $t = asignar_ticket($carnet, $pago['id_pago']);
    if ($t === 'dup') return ['err', 'Pago duplicado', 'Ese número de recibo ya fue usado.'];
    if (!$t) return ['err', 'Sin tickets disponibles', 'Avisa a la Coordinación.'];
    return ['ok', 'Pago validado', 'Tu ticket quedó asignado. Presenta el QR en el ingreso.', $t, $est];
}

/** Tercer momento (port de validar_ingreso_qr). */
function validar_ingreso($codigo, $dia) {
    if (!in_array($dia, [1, 2], true)) return ['err', 'Día inválido', 'El día debe ser 1 o 2.'];
    $r = uno("SELECT t.id_ticket, t.estado AS estado_ticket, v.id_validacion, v.ingreso_dia_1, v.ingreso_dia_2,
                     e.nombre_completo, e.carnet, p.estado_pago
              FROM tickets t
              LEFT JOIN validaciones v ON t.id_ticket=v.id_ticket
              LEFT JOIN estudiantes e ON v.carnet=e.carnet
              LEFT JOIN pagos p ON v.id_pago=p.id_pago
              WHERE t.codigo_qr=?", [$codigo]);
    if (!$r) return ['err', 'Ticket inexistente', 'El código no corresponde a ningún ticket.'];
    if (!in_array($r['estado_ticket'], ['ASIGNADO', 'UTILIZADO'], true) || !$r['id_validacion'])
        return ['err', 'Ticket sin asignar', 'Este ticket no está asignado a ningún estudiante.'];
    $col = "ingreso_dia_$dia";
    if ($r[$col] !== null)
        return ['err', 'Ingreso rechazado', "{$r['nombre_completo']} ya ingresó el día $dia a las " . date('H:i:s', strtotime($r[$col])) . '.'];
    $ahora = date('Y-m-d H:i:s');
    $u = db()->prepare("UPDATE validaciones SET $col=? WHERE id_validacion=? AND $col IS NULL");
    $u->execute([$ahora, $r['id_validacion']]);
    if ($u->rowCount() === 0) return ['err', 'Ingreso rechazado', 'Este ticket acaba de ser utilizado.'];
    db()->prepare("UPDATE tickets SET estado='UTILIZADO' WHERE id_ticket=?")->execute([$r['id_ticket']]);
    return ['ok', 'Ingreso autorizado', "Bienvenido/a, día $dia. Hora: " . date('H:i:s', strtotime($ahora)) . '.',
            ['Nombre' => $r['nombre_completo'], 'Carné' => $r['carnet'], 'Pago' => $r['estado_pago'], 'Ticket' => $r['id_ticket']]];
}

// ---------- Envío del QR por correo (SMTP con STARTTLS, sin librerías) ----------
function smtp_enviar($para, $asunto, $html) {
    $c = SMTP_CFG;
    $ctx = stream_context_create(['ssl' => ['verify_peer' => false, 'verify_peer_name' => false]]); // Windows suele no tener certificados raíz
    $fp = @stream_socket_client("tcp://{$c['host']}:{$c['port']}", $en, $es, 15, STREAM_CLIENT_CONNECT, $ctx);
    if (!$fp) throw new Exception("No se pudo conectar al servidor de correo ($es)");
    $leer = function () use ($fp) { $r = ''; while (($l = fgets($fp, 515)) !== false) { $r .= $l; if (substr($l, 3, 1) === ' ') break; } return $r; };
    $cmd = function ($x, $ok) use ($fp, $leer) {
        if ($x !== null) fwrite($fp, $x . "\r\n");
        $r = $leer(); if (strpos($ok, substr($r, 0, 3)) === false) throw new Exception('SMTP: ' . trim($r)); return $r;
    };
    $cmd(null, '220'); $cmd('EHLO localhost', '250'); $cmd('STARTTLS', '220');
    if (!stream_socket_enable_crypto($fp, true, STREAM_CRYPTO_METHOD_TLS_CLIENT)) throw new Exception('Falló la conexión segura (activa extension=openssl)');
    $cmd('EHLO localhost', '250'); $cmd('AUTH LOGIN', '334');
    $cmd(base64_encode($c['user']), '334'); $cmd(base64_encode($c['password']), '235');
    $cmd("MAIL FROM:<{$c['user']}>", '250'); $cmd("RCPT TO:<$para>", '250 251'); $cmd('DATA', '354');
    $h = "From: =?UTF-8?B?" . base64_encode($c['from_name']) . "?= <{$c['user']}>\r\nTo: <$para>\r\n"
       . "Subject: =?UTF-8?B?" . base64_encode($asunto) . "?=\r\nDate: " . date('r') . "\r\nMIME-Version: 1.0\r\n"
       . "Content-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n";
    fwrite($fp, $h . chunk_split(base64_encode($html)) . "\r\n.\r\n");
    $cmd(null, '250'); $cmd('QUIT', '221'); fclose($fp);
}

function enviar_qr($est, $ticket, $ev) {
    if (empty($est['correo'])) return ['err', 'No hay un correo registrado para tu carné. Avisa a la Coordinación.'];
    $qr = 'https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=' . urlencode($ticket['codigo_qr']);
    $dias = ''; foreach ($ev['dias'] as $i => $d) $dias .= '<li>Día ' . ($i + 1) . ': ' . fecha_larga($d['fecha']) . ', ' . e($d['hora']) . '</li>';
    $html = '<div style="font-family:Arial,sans-serif;max-width:480px"><h2>' . e($ev['nombre']) . '</h2>'
          . '<p>Hola ' . e($est['nombre_completo']) . ', tu pago fue validado. Presenta este QR en el ingreso (sirve para todos los días):</p>'
          . '<p><img src="' . e($qr) . '" width="260" height="260" alt="QR"></p>'
          . '<p>Ticket: <b>' . e($ticket['id_ticket']) . '</b><br>Carné: ' . e($est['carnet']) . '</p><ul>' . $dias . '</ul>'
          . '<p style="color:#666;font-size:12px">' . e($ev['lugar']) . '</p></div>';
    try { smtp_enviar($est['correo'], 'Tu ticket: ' . $ev['nombre'], $html); }
    catch (Throwable $x) { return ['err', 'No se pudo enviar el correo: ' . $x->getMessage()]; }
    [$u, $d] = explode('@', $est['correo'], 2);
    return ['ok', 'Enviamos el QR a ' . substr($u, 0, 2) . '***@' . $d . '. Revisa también el spam.'];
}
