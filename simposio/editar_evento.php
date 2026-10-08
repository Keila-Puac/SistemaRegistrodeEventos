<?php
require_once 'includes/datos.php';
$id = (int)($_GET['id'] ?? 0);
$pos = null;
foreach ($_SESSION['eventos'] as $i => $x) if ($x['id'] == $id) $pos = $i;
if ($pos === null) { header('Location: index.php'); exit; }
$ev = $_SESSION['eventos'][$pos];
$error = false;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $dias = [];
    foreach ($_POST['fecha'] ?? [] as $i => $f)
        if ($f) $dias[] = ['fecha' => $f, 'hora' => $_POST['hora'][$i] ?? '08:00', 'desc' => $_POST['desc'][$i] ?? ''];
    if (trim($_POST['nombre'] ?? '') && $dias) {
        $_SESSION['eventos'][$pos] = array_merge($ev, [
            'nombre' => trim($_POST['nombre']), 'lema' => trim($_POST['lema']), 'lugar' => trim($_POST['lugar']),
            'precio' => (float)$_POST['precio'], 'cupo' => max((int)$_POST['cupo'], $ev['inscritos']), 'dias' => $dias,
        ]);
        header("Location: evento.php?id=$id&editado=1"); exit;
    }
    $error = true;
    $ev = array_merge($ev, ['nombre' => $_POST['nombre'] ?? '']); // conserva lo escrito
}
$titulo = 'Modificar evento'; require 'includes/header.php'; ?>
<section class="cabecera"><h1>Modificar evento</h1></section>
<?php if ($error): ?><p class="aviso err">Escribe el nombre del evento y deja al menos un día con fecha.</p><?php endif; ?>
<form method="post" class="form ancho">
  <label>Nombre del evento<input name="nombre" required value="<?= e($ev['nombre']) ?>"></label>
  <label>Lema<input name="lema" value="<?= e($ev['lema']) ?>"></label>
  <label>Lugar<input name="lugar" value="<?= e($ev['lugar']) ?>"></label>
  <div class="fila">
    <label>Precio por estudiante (Q)<input type="number" name="precio" min="0" step="0.01" value="<?= e($ev['precio']) ?>"></label>
    <label>Cupo de tickets<input type="number" name="cupo" min="<?= (int)$ev['inscritos'] ?>" value="<?= e($ev['cupo']) ?>"></label>
  </div>
  <p class="meta">El cupo no puede ser menor a los <?= (int)$ev['inscritos'] ?> tickets ya asignados.</p>
  <fieldset>
    <legend>Días del evento</legend>
    <div id="dias">
      <?php foreach ($ev['dias'] as $d): ?>
      <div class="fila dia-form">
        <label>Fecha<input type="date" name="fecha[]" value="<?= e($d['fecha']) ?>"></label>
        <label>Hora de inicio<input type="time" name="hora[]" value="<?= e($d['hora']) ?>"></label>
        <label class="grande">Programa del día<input name="desc[]" value="<?= e($d['desc']) ?>"></label>
        <button type="button" class="btn sec quitar">Quitar día</button>
      </div>
      <?php endforeach; ?>
    </div>
    <button type="button" class="btn sec" id="mas">Agregar otro día</button>
    <p class="meta">Un día sin fecha se elimina al guardar.</p>
  </fieldset>
  <div class="acciones"><button class="btn">Guardar cambios</button><a href="evento.php?id=<?= $id ?>">Cancelar</a></div>
</form>
<script>
const cont = document.getElementById('dias');
document.getElementById('mas').onclick = () => {
  const c = cont.querySelector('.dia-form').cloneNode(true);
  c.querySelectorAll('input').forEach(i => { if (i.type !== 'time') i.value = ''; });
  cont.appendChild(c);
};
cont.addEventListener('click', e => {
  if (e.target.classList.contains('quitar') && cont.children.length > 1) e.target.closest('.dia-form').remove();
});
</script>
<?php require 'includes/footer.php'; ?>
