<?php
// Configuración común: define estas variables en el servidor; no guardes contraseñas aquí.
$env = static function ($name, $default = '') {
    $value = getenv($name);
    return ($value === false || $value === '') ? $default : $value;
};
define('DB_CFG', [
    'host' => $env('DB_HOST', 'mysql-jack-vg.alwaysdata.net'),
    'port' => (int)$env('DB_PORT', '3306'),
    'user' => $env('DB_USER', 'jack-vg'),
    'database' => $env('DB_NAME', 'jack-vg_simposio_db'),
    'password' => $env('DB_PASSWORD'),
]);
define('SMTP_CFG', [
    'host' => $env('SMTP_HOST', 'smtp.gmail.com'),
    'port' => (int)$env('SMTP_PORT', '587'),
    'user' => $env('SMTP_USER'),
    'password' => $env('SMTP_PASSWORD'),
    'from_name' => $env('SMTP_FROM_NAME', 'Simposio de Ingeniería URL'),
]);
// Cambia el PIN desde la variable de entorno PIN_PERSONAL.
define('PIN_PERSONAL', $env('PIN_PERSONAL', '2468'));
