<?php require_once __DIR__ . '/datos.php'; $pagina = basename($_SERVER['SCRIPT_NAME']); ?>
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($titulo ?? 'Eventos') ?> · Simposio URL</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Public+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="top">
  <a class="marca" href="index.php"><img src="assets/logo.png" alt="Universidad Rafael Landívar"><span>Registro de eventos</span></a>
  <nav>
    <a href="index.php" <?= $pagina=='index.php'?'aria-current="page"':'' ?>>Eventos</a>
    <a href="crear_evento.php" <?= $pagina=='crear_evento.php'?'aria-current="page"':'' ?>>Crear evento</a>
    <a href="ingreso.php" <?= $pagina=='ingreso.php'?'aria-current="page"':'' ?>>Control de ingreso</a>
  </nav>
</header>
<main>
