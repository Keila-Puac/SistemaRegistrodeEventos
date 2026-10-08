<?php
require_once 'includes/datos.php';
$ev = buscar_evento($_GET['id'] ?? 1);
if (!$ev) { header('Location: index.php'); exit; }
// Resultado de ejemplo para la interfaz (la lógica real irá con la BD/AFD)
$res = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $c = trim($_POST['carnet'] ?? ''); $r = trim($_POST['recibo'] ?? '');
    if (!$c || !$r)            $res = ['info','Información incompleta','Escribe tu carné y el número de recibo.'];
    elseif ($r === '000')      $res = ['err','Pago no localizado','No encontramos ese recibo en el reporte de Tesorería.'];
    elseif ($r === '111')      $res = ['warn','Enviado a revisión manual','Encontramos más de una posible coincidencia. La Coordinación lo revisará.'];
    else                       $res = ['ok','Pago validado','Tu ticket quedó asignado. Presenta este código en el ingreso.'];
}
$titulo = $ev['nombre']; require 'includes/header.php'; ?>
<?php if (isset($_GET['nuevo'])): ?><p class="aviso ok">Evento creado.</p><?php endif; ?>
<section class="portada">
  <p class="meta"><?= e($ev['lugar']) ?></p>
  <h1><?= e($ev['nombre']) ?></h1>
  <p class="lema"><?= e($ev['lema']) ?></p>
</section>
<div class="dos">
  <section>
    <h2>Programa</h2>
    <ol class="dias">
    <?php foreach ($ev['dias'] as $i => $d): ?>
      <li><h3>Día <?= $i+1 ?>: <?= fecha_larga($d['fecha']) ?></h3>
          <p class="meta">Inicia a las <?= e($d['hora']) ?></p><p><?= e($d['desc']) ?></p></li>
    <?php endforeach; ?>
    </ol>
    <p class="meta">Un mismo ticket da acceso a los <?= count($ev['dias']) ?> días. El ingreso se registra por día.</p>
  </section>
  <section class="panel">
    <h2>Valida tu pago</h2>
    <?php if ($res && $res[0]==='ok'): ?>
      <div class="aviso ok"><b><?= $res[1] ?></b><br><?= $res[2] ?></div>
      <div class="ticket">
        <div class="qr" aria-label="Código QR de ejemplo"></div>
        <div><b>TKT-0001</b><br><?= e($_POST['carnet']) ?><br>Recibo <?= e($_POST['recibo']) ?><br><small><?= e($ev['nombre']) ?></small></div>
      </div>
      <button class="btn sec" onclick="window.print()">Guardar confirmación</button>
    <?php else: ?>
      <?php if ($res): ?><div class="aviso <?= $res[0] ?>"><b><?= $res[1] ?></b><br><?= $res[2] ?></div><?php endif; ?>
      <form method="post" class="form">
        <label>Número de carné<input name="carnet" value="<?= e($_POST['carnet'] ?? '') ?>" placeholder="1234567"></label>
        <label>Número de recibo<input name="recibo" value="<?= e($_POST['recibo'] ?? '') ?>"></label>
        <label>Correo institucional (opcional)<input type="email" name="correo"></label>
        <button class="btn">Validar pago</button>
      </form>
      <p class="meta">Prueba: recibo 000 = no localizado, 111 = revisión manual.</p>
    <?php endif; ?>
  </section>
</div>
<?php require 'includes/footer.php'; ?>
