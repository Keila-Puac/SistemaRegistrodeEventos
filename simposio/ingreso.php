<?php
require_once 'includes/datos.php';
require_once 'includes/db.php';
$ev = $_SESSION['eventos'][0];
$res = null; $dia = (int)($_POST['dia'] ?? 1);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $cod = trim($_POST['codigo'] ?? '');
    if ($cod === '') $res = ['err', 'Falta el código', 'Escanea el QR o escribe el código del ticket.'];
    else try { $res = validar_ingreso($cod, $dia); }
    catch (Throwable $x) { $res = ['err', 'Error de base de datos', $x->getMessage()]; }
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
    <button type="button" class="btn sec" id="btn-cam">Escanear con cámara</button>
    <div id="lector" hidden></div>
    <p class="aviso err" id="cam-error" hidden></p>
    <label>O escribe el código del ticket<input name="codigo" id="codigo" autocomplete="off" placeholder="TKT-0001"></label>
    <button class="btn">Validar ingreso</button>
  </form>
  <section class="resultado <?= $res ? ($res[0] === 'ok' ? 'ok' : 'err') : '' ?>" aria-live="polite">
    <?php if ($res): ?>
      <h2><?= e($res[1]) ?></h2><p><?= e($res[2]) ?></p>
      <?php if (!empty($res[3])): ?><dl><?php foreach ($res[3] as $k => $v): ?><dt><?= e($k) ?></dt><dd><?= e($v) ?></dd><?php endforeach; ?></dl><?php endif; ?>
    <?php else: ?><p class="meta">El resultado aparece aquí.</p><?php endif; ?>
  </section>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js"></script>
<script>
const btn = document.getElementById('btn-cam'), caja = document.getElementById('lector'),
      err = document.getElementById('cam-error'), campo = document.getElementById('codigo');
let lector = null;
async function cerrar() {
  if (lector) { try { await lector.stop(); } catch (e) {} lector = null; }
  caja.hidden = true; btn.textContent = 'Escanear con cámara';
}
btn.onclick = async () => {
  if (lector) return cerrar();
  err.hidden = true; caja.hidden = false;
  lector = new Html5Qrcode('lector');
  try {
    await lector.start({ facingMode: 'environment' }, { fps: 10, qrbox: 240 }, async texto => {
      campo.value = texto.trim();
      await cerrar();
      campo.form.submit();            // valida de inmediato con el día elegido
    });
    btn.textContent = 'Cerrar cámara';
  } catch (e) {
    lector = null; caja.hidden = true;
    err.textContent = 'No se pudo abrir la cámara. Permite el acceso en el navegador o escribe el código.';
    err.hidden = false;
  }
};
</script>
<?php require 'includes/footer.php'; ?>
