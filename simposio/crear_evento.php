<?php
require_once 'includes/datos.php';
$ok = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $dias = [];
    foreach ($_POST['fecha'] ?? [] as $i => $f)
        if ($f) $dias[] = ['fecha' => $f, 'hora' => $_POST['hora'][$i] ?? '08:00', 'desc' => $_POST['desc'][$i] ?? ''];
    if (trim($_POST['nombre'] ?? '') && $dias) {
        $id = count($_SESSION['eventos']) + 1;
        $_SESSION['eventos'][] = ['id'=>$id,'nombre'=>trim($_POST['nombre']),'lema'=>trim($_POST['lema']),
            'lugar'=>trim($_POST['lugar']),'precio'=>(float)$_POST['precio'],'cupo'=>(int)$_POST['cupo'],'inscritos'=>0,'dias'=>$dias];
        header("Location: evento.php?id=$id&nuevo=1"); exit;
    }
    $ok = false;
}
$titulo = 'Crear evento'; require 'includes/header.php'; ?>
<section class="cabecera"><h1>Crear evento</h1></section>
<?php if ($ok === false): ?><p class="aviso err">Escribe el nombre del evento y agrega al menos un día con fecha.</p><?php endif; ?>
<form method="post" class="form ancho">
  <label>Nombre del evento<input name="nombre" required placeholder="XX Simposio de Ingeniería"></label>
  <label>Lema<input name="lema"></label>
  <label>Lugar<input name="lugar"></label>
  <div class="fila">
    <label>Precio por estudiante (Q)<input type="number" name="precio" min="0" step="0.01" value="0"></label>
    <label>Cupo de tickets<input type="number" name="cupo" min="1" value="100"></label>
  </div>
  <fieldset>
    <legend>Días del evento</legend>
    <div id="dias">
      <div class="fila dia-form">
        <label>Fecha<input type="date" name="fecha[]" required></label>
        <label>Hora de inicio<input type="time" name="hora[]" value="08:00"></label>
        <label class="grande">Programa del día<input name="desc[]"></label>
      </div>
    </div>
    <button type="button" class="btn sec" id="mas">Agregar otro día</button>
  </fieldset>
  <div class="acciones"><button class="btn">Guardar evento</button><a href="index.php">Cancelar</a></div>
</form>
<script>
document.getElementById('mas').onclick = () => {
  const c = document.querySelector('.dia-form').cloneNode(true);
  c.querySelectorAll('input').forEach(i => { if (i.type !== 'time') i.value = ''; });
  document.getElementById('dias').appendChild(c);
};
</script>
<?php require 'includes/footer.php'; ?>
