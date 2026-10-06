<?php
declare(strict_types=1);

// Server-to-server transactional mail only. Secret and replay state are outside
// the public web root. The endpoint never accepts arbitrary mail headers.
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
function respond(int $status, bool $accepted = false): never {
    http_response_code($status);
    echo json_encode(['accepted' => $accepted]);
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') respond(405);
if (!str_starts_with(strtolower($_SERVER['CONTENT_TYPE'] ?? ''), 'application/json')) respond(415);
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 512000) respond(413);
$raw = file_get_contents('php://input', false, null, 0, 512001);
if ($raw === false || strlen($raw) > 512000) respond(413);
$timestamp = $_SERVER['HTTP_X_TAFOLLI_TIMESTAMP'] ?? '';
$nonce = $_SERVER['HTTP_X_TAFOLLI_NONCE'] ?? '';
$signature = $_SERVER['HTTP_X_TAFOLLI_SIGNATURE'] ?? '';
if (!ctype_digit($timestamp) || abs(time() - (int)$timestamp) > 60) respond(401);
if (!preg_match('/^[A-Za-z0-9_-]{20,100}$/D', $nonce) || !preg_match('/^[a-f0-9]{64}$/D', $signature)) respond(401);
$private = getenv('TAFOLLIBOOST_MAIL_STATE') ?: dirname(__DIR__, 2) . '/.tafolliboost-mail';
$secretFile = $private . '/relay-secret';
if (!is_file($secretFile) || is_link($secretFile) || (fileperms($secretFile) & 0777) !== 0600) respond(503);
$secret = trim((string)file_get_contents($secretFile));
if (strlen($secret) < 32 || !hash_equals(hash_hmac('sha256', $timestamp . "\n" . $nonce . "\n" . $raw, $secret), $signature)) respond(401);
try { $payload = json_decode($raw, true, 8, JSON_THROW_ON_ERROR); } catch (Throwable $error) { respond(422); }
if (!is_array($payload) || array_diff(array_keys($payload), ['recipient', 'subject', 'text', 'html'])) respond(422);
$to = $payload['recipient'] ?? null;
$subject = $payload['subject'] ?? null;
$text = $payload['text'] ?? null;
if (!is_string($to) || strlen($to) > 254 || !filter_var($to, FILTER_VALIDATE_EMAIL)) respond(422);
if (!is_string($subject) || strlen($subject) > 500 || $subject === '' || preg_match('/[\x00-\x1f\x7f]/', $subject)) respond(422);
if (!is_string($text) || strlen($text) < 1 || strlen($text) > 200000 || strpos($text, "\0") !== false) respond(422);
$htmlBody = $payload['html'] ?? '';
if (!is_string($htmlBody) || strlen($htmlBody) > 300000 || strpos($htmlBody, "\0") !== false) respond(422);
$state = fopen($private . '/replay.json', 'c+');
if ($state === false || !flock($state, LOCK_EX)) respond(503);
chmod($private . '/replay.json', 0600);
$entries = json_decode(stream_get_contents($state), true) ?: [];
$entries = array_filter($entries, static fn($issued) => is_int($issued) && $issued >= time() - 120);
if (isset($entries[$nonce])) { flock($state, LOCK_UN); fclose($state); respond(409); }
if (count($entries) >= 100) { flock($state, LOCK_UN); fclose($state); respond(429); }
$entries[$nonce] = time();
rewind($state); ftruncate($state, 0); fwrite($state, json_encode($entries)); fflush($state);
flock($state, LOCK_UN); fclose($state);
$boundary = 'tafolliboost-' . bin2hex(random_bytes(18));
$headers = [
    'From' => 'TafolliBoost <info@tafolli.net>',
    'Reply-To' => 'info@tafolli.net',
    'MIME-Version' => '1.0',
    'Content-Type' => $htmlBody === '' ? 'text/plain; charset=UTF-8' : 'multipart/alternative; boundary="' . $boundary . '"',
    'Auto-Submitted' => 'auto-generated',
];
$encodedSubject = '=?UTF-8?B?' . base64_encode($subject) . '?=';
$body = chunk_split(base64_encode($text), 76, "\r\n");
if ($htmlBody === '') {
    $headers['Content-Transfer-Encoding'] = 'base64';
} else {
    $body = '--' . $boundary . "\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" . $body
        . '--' . $boundary . "\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
        . chunk_split(base64_encode($htmlBody), 76, "\r\n") . '--' . $boundary . "--\r\n";
}
$sent = mail($to, $encodedSubject, $body, $headers, '-finfo@tafolli.net');
respond($sent ? 200 : 503, $sent);
