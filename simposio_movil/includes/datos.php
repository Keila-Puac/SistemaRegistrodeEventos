<?php
// SOLO INTERFAZ: datos de ejemplo en sesión. Aquí se conectará la BD después.
date_default_timezone_set('America/Guatemala'); // hora real de Guatemala (antes usaba UTC)
session_start();
if (!isset($_SESSION['eventos'])) {
    $_SESSION['eventos'] = [[
        'id' => 1,
        'nombre' => 'XIX Simposio de Ingeniería',
        'lema' => 'De la gestión inteligente a la acción en ingeniería',
        'lugar' => 'Facultad de Ingeniería, Campus Quetzaltenango',
        'precio' => 75, 'cupo' => 300, 'inscritos' => 128,
        'dias' => [
            ['fecha' => '2026-11-05', 'hora' => '08:00', 'desc' => 'Inauguración, conferencia magistral y panel de gestión inteligente'],
            ['fecha' => '2026-11-06', 'hora' => '08:30', 'desc' => 'Talleres de acción en ingeniería y clausura'],
        ],
    ]];
}

function e($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function buscar_evento($id) {
    foreach ($_SESSION['eventos'] as $ev) if ($ev['id'] == $id) return $ev;
    return null;
}
function fecha_larga($f) {
    $m = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
    $t = strtotime($f);
    return date('j', $t) . ' de ' . $m[date('n', $t) - 1] . ' de ' . date('Y', $t);
}
