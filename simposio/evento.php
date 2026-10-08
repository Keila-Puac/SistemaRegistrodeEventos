<?php
require_once 'includes/datos.php';
require_once 'includes/db.php';
$ev = buscar_evento($_GET['id'] ?? 1);
if (!$ev) { header('Location: index.php'); exit; }

$res = null; $envio = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $c = trim($_POST['carnet'] ?? ''); $r = trim($_POST['recibo'] ?? '');
    if (!$c || !$r) $res = ['info', 'Información incompleta', 'Escribe tu carné y el número de recibo.'];
    else try {
        $res = procesar_validacion($c, $r);
        if ($res[0] === 'ok' && !empty($_POST['enviar'])) $envio = enviar_qr($res[4], $res[3], $ev);
    } catch (Throwable $x) {
        $res = ['err', 'No se pudo completar la validación', 'Revisa includes/config.php y que pdo_mysql esté activo. Detalle: ' . $x->getMessage()];
    }
}
$titulo = $ev['nombre']; require 'includes/header.php'; ?>
<?php if (isset($_GET['nuevo'])): ?><p class="aviso ok">Evento creado.</p><?php endif; ?>
<?php if (isset($_GET['editado'])): ?><p class="aviso ok">Cambios guardados.</p><?php endif; ?>
<section class="portada">
  <p class="meta"><?= e($ev['lugar']) ?></p>
  <h1><?= e($ev['nombre']) ?></h1>
  <a class="btn sec" href="editar_evento.php?id=<?= $ev['id'] ?>">Modificar evento</a>
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
    <?php if ($res && $res[0] === 'ok'): $t = $res[3]; $est = $res[4]; ?>
      <div class="aviso ok"><b><?= e($res[1]) ?></b><br><?= e($res[2]) ?></div>
      <div class="ticket">
        <div class="qr" id="qr" aria-label="Código QR del ticket <?= e($t['id_ticket']) ?>"></div>
        <div><b><?= e($t['id_ticket']) ?></b><br><?= e($est['nombre_completo']) ?><br>Carné <?= e($est['carnet']) ?><br><small><?= e($ev['nombre']) ?></small></div>
      </div>
      <?php if ($envio): ?><p class="aviso <?= $envio[0] ?>"><?= e($envio[1]) ?></p><?php endif; ?>
      <form method="post" class="acciones">
        <input type="hidden" name="carnet" value="<?= e($_POST['carnet']) ?>">
        <input type="hidden" name="recibo" value="<?= e($_POST['recibo']) ?>">
        <button class="btn" name="enviar" value="1">Enviar QR a mi correo</button>
        <button type="button" class="btn sec" onclick="window.print()">Guardar confirmación</button>
      </form>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
      <script>new QRCode(document.getElementById('qr'), { text: <?= json_encode($t['codigo_qr']) ?>, width: 100, height: 100 });</script>
    <?php else: ?>
      <?php if ($res): ?><div class="aviso <?= $res[0] ?>"><b><?= e($res[1]) ?></b><br><?= e($res[2]) ?></div><?php endif; ?>
      <form method="post" class="form">
        <label>Número de carné<input name="carnet" value="<?= e($_POST['carnet'] ?? '') ?>"></label>
        <label>Número de recibo<input name="recibo" value="<?= e($_POST['recibo'] ?? '') ?>"></label>
        <button class="btn">Validar pago</button>
      </form>
    <?php endif; ?>
  </section>
</div>
<?php require 'includes/footer.php'; ?>
