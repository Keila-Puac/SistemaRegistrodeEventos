<?php
require_once 'includes/datos.php';
$ev = $_SESSION['eventos'][0];
$res = null; $dia = (int)($_POST['dia'] ?? 1);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $cod = strtoupper(trim($_POST['codigo'] ?? ''));
    $llave = "$cod|$dia";
    if (!preg_match('/^TKT-\d{4}$/', $cod))          $res = ['err','Ticket inexistente','El código no corresponde a ningún ticket.'];
    elseif (isset($_SESSION['usados'][$llave]))      $res = ['err','Ingreso rechazado','Este ticket ya ingresó el día '.$dia.' a las '.$_SESSION['usados'][$llave].'.'];
    else { $_SESSION['usados'][$llave] = date('H:i:s'); $res = ['ok','Ingreso autorizado','Bienvenido al día '.$dia.'.']; }
}
$titulo = 'Control de ingreso'; require 'includes/header.php'; ?>
<section class="cabecera"><h1>Control de ingreso</h1></section>
<div class="dos">
  <form method="post" class="form">
    <fieldset class="seg"><legend>Día del evento</legend>
      <?php foreach ($ev['dias'] as $i => $d): ?>
        <label><input type="radio" name="dia" value="<?= $i+1 ?>" <?= $dia==$i+1?'checked':'' ?>> Día <?= $i+1 ?> · <?= date('d/m', strtotime($d['fecha'])) ?></label>
      <?php endforeach; ?>
    </fieldset>
    <label>Escanea el QR o escribe el ticket<input name="codigo" autofocus autocomplete="off" placeholder="TKT-0001"></label>
    <button class="btn">Validar ingreso</button>
  </form>
  <section class="resultado <?= $res ? $res[0] : '' ?>" aria-live="polite">
    <?php if ($res): ?>
      <h2><?= $res[1] ?></h2><p><?= $res[2] ?></p>
      <?php if ($res[0]==='ok'): ?>
        <dl><dt>Nombre</dt><dd>Estudiante de ejemplo</dd><dt>Carné</dt><dd>1234567</dd><dt>Pago</dt><dd>Validado</dd><dt>Ticket</dt><dd><?= e($cod) ?></dd></dl>
      <?php endif; ?>
    <?php else: ?><p class="meta">El resultado aparece aquí. Prueba con TKT-0001 dos veces.</p><?php endif; ?>
  </section>
</div>
<?php require 'includes/footer.php'; ?>
