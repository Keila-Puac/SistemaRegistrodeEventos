<?php
date_default_timezone_set('America/Guatemala');

define('DB_CFG', [
    'host' => 'mysql-jack-vg.alwaysdata.net',
    'port' => 3306,
    'user' => 'TU_USUARIO',
    'database' => 'TU_BASE_DE_DATOS',
    'password' => 'TU_CONTRASEÑA'
]);

define('SMTP_CFG', [
    'host' => 'smtp.gmail.com',
    'port' => 587,
    'user' => 'TU_CORREO',
    'password' => 'TU_CLAVE_DE_APLICACION',
    'from_name' => 'Simposio de Ingeniería'
]);s