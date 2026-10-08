<?php
// Configuración. NO subas este archivo a GitHub (agrégalo a .gitignore).
define('DB_CFG', [
    'host' => 'mysql-jack-vg.alwaysdata.net', 'port' => 3306,
    'user' => 'jack-vg', 'database' => 'jack-vg_simposio_db',
    'password' => getenv('DB_PASS') ?: 'ESCRIBE_AQUI_TU_CONTRASEÑA',
]);
// Correo que ENVÍA los QR (ejemplo con Gmail + "contraseña de aplicación")
define('SMTP_CFG', [
    'host' => 'smtp.gmail.com', 'port' => 587,
    'user' => 'tucorreo@gmail.com', 'password' => 'CONTRASEÑA_DE_APLICACION',
    'from_name' => 'Simposio de Ingeniería URL',
]);
// PIN que el personal escribe para abrir la versión móvil de control de ingreso (cámbialo).
define('PIN_PERSONAL', '2468');
