<?php
require_once 'includes/datos.php';
require_once 'includes/config.php';
$ev = $_SESSION['eventos'][0];
if (isset($_GET['salir'])) { unset($_SESSION['personal']); header('Location: control_movil.php'); exit; }
$pin_mal = false;
if (isset($_POST['pin'])) {
    if (hash_equals(PIN_PERSONAL, trim($_POST['pin']))) $_SESSION['personal'] = true; else $pin_mal = true;
}
$dia_hoy = 1; foreach ($ev['dias'] as $i => $d) if ($d['fecha'] === date('Y-m-d')) $dia_hoy = $i + 1;
?><!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#14213a">
<title>Control de ingreso</title>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,800&family=Public+Sans:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{--tinta:#14213a;--azul:#0b4a8f;--ok:#1d7a46;--err:#b3261e}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{height:100%;margin:0}
body{background:var(--tinta);color:#fff;font:600 17px 'Public Sans',system-ui,sans-serif;display:flex;flex-direction:column;
 padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)}
h1{font:800 1.3rem Fraunces,serif;margin:0}
.barra{display:flex;justify-content:space-between;align-items:center;padding:.8rem 1rem;gap:.5rem}
.barra small{display:block;font-weight:500;opacity:.75}
.barra a{color:#fff;opacity:.8;font-size:.9rem}
.dias{display:flex;gap:.5rem;padding:0 1rem .8rem}
.dias button{flex:1;padding:.9rem;border-radius:10px;border:2px solid #fff5;background:transparent;color:#fff;font:inherit}
.dias button[aria-pressed=true]{background:#fff;color:var(--tinta);border-color:#fff}
#visor{flex:1;min-height:0;position:relative;background:#000;display:grid;place-items:center}
#lector{width:100%}
#msg{padding:1.5rem;text-align:center;font-weight:500}
.pie{display:flex;gap:.6rem;padding:.8rem 1rem;align-items:center}
.pie input{flex:1;min-width:0;font:inherit;padding:.85rem;border-radius:10px;border:0;color:var(--tinta)}
.pie button,.btn{padding:.85rem 1.1rem;border-radius:10px;border:0;background:var(--azul);color:#fff;font:inherit}
.cont{text-align:center;font-weight:500;opacity:.85;padding-bottom:.6rem}
#res{position:fixed;inset:0;display:none;flex-direction:column;justify-content:center;padding:2rem;text-align:center;z-index:9}
#res.ok{background:var(--ok)}#res.err{background:var(--err)}
#res h2{font:800 2.2rem/1.1 Fraunces,serif;margin:0 0 .75rem}
#res p{font-size:1.15rem;margin:.2rem 0}
#res dl{display:grid;grid-template-columns:auto 1fr;gap:.4rem 1rem;text-align:left;max-width:360px;margin:1.5rem auto 0;font-weight:500}
#res dt{opacity:.8}#res dd{margin:0;font-weight:600}
#res small{margin-top:2rem;opacity:.8}
.pin{margin:auto;width:min(340px,90%);display:grid;gap:1rem;text-align:center}
.pin input{font:inherit;font-size:1.6rem;text-align:center;letter-spacing:.4rem;padding:.8rem;border-radius:10px;border:0}
:focus-visible{outline:3px solid #f2a900;outline-offset:2px}
</style>
</head>
<body>
<?php if (empty($_SESSION['personal'])): ?>
  <form method="post" class="pin">
    <h1>Control de ingreso</h1>
    <p><?= e($ev['nombre']) ?></p>
    <input type="password" name="pin" inputmode="numeric" autocomplete="off" placeholder="PIN" autofocus aria-label="PIN del personal">
    <?php if ($pin_mal): ?><p>PIN incorrecto. Inténtalo de nuevo.</p><?php endif; ?>
    <button class="btn">Entrar</button>
  </form>
<?php else: ?>
  <div class="barra">
    <div><h1>Control de ingreso</h1><small><?= e($ev['nombre']) ?></small></div>
    <a href="?salir=1">Salir</a>
  </div>
  <div class="dias" role="group" aria-label="Día del evento">
    <?php foreach ($ev['dias'] as $i => $d): ?>
      <button type="button" data-dia="<?= $i+1 ?>" aria-pressed="<?= $i+1 == $dia_hoy ? 'true' : 'false' ?>">Día <?= $i+1 ?> · <?= date('d/m', strtotime($d['fecha'])) ?></button>
    <?php endforeach; ?>
  </div>
  <div id="visor"><div id="lector"></div><p id="msg">Abriendo cámara…</p></div>
  <div class="cont">Ingresos autorizados: <span id="n">0</span></div>
  <form class="pie" id="manual">
    <input id="codigo" placeholder="Código del ticket" autocomplete="off" autocapitalize="off" aria-label="Código del ticket">
    <button>Validar</button>
  </form>
  <div id="res" role="alert"><h2 id="r-t"></h2><p id="r-x"></p><dl id="r-d"></dl><small>Toca para seguir escaneando</small></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/html5-qrcode/2.3.8/html5-qrcode.min.js"></script>
<script>
let dia = <?= (int)$dia_hoy ?>, ocupado = false, ultimo = '', tUltimo = 0, n = 0, cierre;
const $ = id => document.getElementById(id), res = $('res');

document.querySelectorAll('[data-dia]').forEach(b => b.onclick = () => {
  dia = +b.dataset.dia;
  document.querySelectorAll('[data-dia]').forEach(x => x.setAttribute('aria-pressed', x === b));
});

function cerrar() { clearTimeout(cierre); res.style.display = 'none'; ocupado = false; }
res.onclick = cerrar;

async function validar(codigo) {
  if (ocupado) return; ocupado = true;
  let r;
  try {
    const f = await fetch('api_ingreso.php', { method: 'POST', body: new URLSearchParams({ codigo, dia }) });
    r = await f.json();
  } catch (e) { r = { ok: false, titulo: 'Sin conexión', texto: 'Revisa tu internet y vuelve a escanear.' }; }
  res.className = r.ok ? 'ok' : 'err';
  $('r-t').textContent = r.titulo; $('r-x').textContent = r.texto;
  const dl = $('r-d'); dl.innerHTML = '';
  for (const [k, v] of Object.entries(r.datos || {})) {
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = k; dd.textContent = v; dl.append(dt, dd);
  }
  res.style.display = 'flex';
  if (r.ok) { $('n').textContent = ++n; navigator.vibrate && navigator.vibrate(120); }
  else navigator.vibrate && navigator.vibrate([200, 100, 200]);
  cierre = setTimeout(cerrar, r.ok ? 2500 : 4000);
}

$('manual').onsubmit = e => { e.preventDefault(); const c = $('codigo').value.trim(); if (c) { $('codigo').value = ''; validar(c); } };

const lector = new Html5Qrcode('lector');
lector.start({ facingMode: 'environment' },
  { fps: 10, qrbox: (w, h) => { const l = Math.floor(Math.min(w, h) * 0.75); return { width: l, height: l }; } },
  texto => {
    const ahora = Date.now();
    if (texto === ultimo && ahora - tUltimo < 4000) return;   // evita lecturas repetidas del mismo QR
    ultimo = texto; tUltimo = ahora; validar(texto.trim());
  })
  .then(() => $('msg').remove())
  .catch(() => { $('msg').textContent = 'No se pudo abrir la cámara. Permite el acceso en el navegador (la página debe abrirse con https) o escribe el código abajo.'; });
</script>
<?php endif; ?>
</body>
</html>
