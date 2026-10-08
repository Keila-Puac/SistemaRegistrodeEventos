<?php $titulo = 'Eventos'; require 'includes/header.php'; ?>
<section class="cabecera">
  <h1>Eventos</h1>
  <a class="btn" href="crear_evento.php">Crear evento</a>
</section>
<div class="lista">
<?php foreach ($_SESSION['eventos'] as $ev):
  $pct = round($ev['inscritos'] / max(1,$ev['cupo']) * 100); ?>
  <article class="evento">
    <div class="evento-fechas">
      <?php foreach ($ev['dias'] as $i => $d): ?>
        <div class="dia"><b><?= date('j', strtotime($d['fecha'])) ?></b><small>Día <?= $i+1 ?></small></div>
      <?php endforeach; ?>
    </div>
    <div class="evento-cuerpo">
      <h2><a href="evento.php?id=<?= $ev['id'] ?>"><?= e($ev['nombre']) ?></a></h2>
      <p><?= e($ev['lema']) ?></p>
      <p class="meta"><?= count($ev['dias']) ?> días · <?= e($ev['lugar']) ?> · Q<?= number_format($ev['precio'],2) ?></p>
      <div class="barra" role="img" aria-label="<?= $pct ?>% de cupo ocupado"><i style="width:<?= $pct ?>%"></i></div>
      <p class="meta"><?= $ev['inscritos'] ?> de <?= $ev['cupo'] ?> tickets asignados</p>
    </div>
    <div class="acc-card">
      <a class="btn sec" href="evento.php?id=<?= $ev['id'] ?>">Ver evento</a>
      <a class="btn sec" href="editar_evento.php?id=<?= $ev['id'] ?>">Modificar</a>
    </div>
  </article>
<?php endforeach; ?>
</div>
<?php require 'includes/footer.php'; ?>
