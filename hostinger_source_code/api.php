<?php
/**
 * LyrFlow - PHP Backend for Hostinger
 * Handles lyrics fetching (lyrics.ovh) + OpenAI processing
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ── Config ─────────────────────────────────────────────────────────────────

define('OPENAI_KEY', getenv('OPENAI_API_KEY') ?: 'YOUR_API_KEY_HERE');
define('CHUNK_SIZE', 20);

// ── Router ─────────────────────────────────────────────────────────────────

$route = $_GET['route'] ?? '';

switch ($route) {
    case 'demos':
        serveDemos();
        break;
    case 'process':
        handleProcess();
        break;
    default:
        http_response_code(404);
        echo json_encode(['error' => 'Unknown route']);
}

// ── Demos endpoint ─────────────────────────────────────────────────────────

function serveDemos() {
    $cacheFile = __DIR__ . '/demo_cache.json';
    if (file_exists($cacheFile)) {
        echo file_get_contents($cacheFile);
    } else {
        echo '{}';
    }
}

// ── Process endpoint ───────────────────────────────────────────────────────

function handleProcess() {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        http_response_code(405);
        echo json_encode(['error' => 'POST required']);
        return;
    }

    $input = json_decode(file_get_contents('php://input'), true);
    $artist = trim($input['artist'] ?? '');
    $title = trim($input['title'] ?? '');

    if (!$artist || !$title) {
        http_response_code(400);
        echo json_encode(['error' => 'Artist and title are required']);
        return;
    }

    // Check demo cache first
    $cacheFile = __DIR__ . '/demo_cache.json';
    if (file_exists($cacheFile)) {
        $cache = json_decode(file_get_contents($cacheFile), true);
        $key = $artist . '||' . $title;
        if (isset($cache[$key])) {
            echo json_encode($cache[$key], JSON_UNESCAPED_UNICODE);
            return;
        }
    }

    // Step 1: Fetch lyrics from lyrics.ovh
    $lyrics = fetchLyrics($artist, $title);
    if (!$lyrics) {
        http_response_code(404);
        echo json_encode(['error' => "Lyrics not found for '$title' by '$artist'"]);
        return;
    }

    // Step 2: Clean lyrics
    $lines = cleanLyrics($lyrics);
    if (empty($lines)) {
        http_response_code(404);
        echo json_encode(['error' => 'No lyrics content found']);
        return;
    }

    // Step 3: Process with OpenAI (parallel chunks)
    $processed = processWithOpenAI($lines);
    if ($processed === null) {
        http_response_code(500);
        echo json_encode(['error' => 'OpenAI processing failed']);
        return;
    }

    // Step 4: Build output
    $langCounts = [];
    foreach ($processed as $l) {
        $base = str_replace('-mixed', '', $l['language'] ?? 'en');
        if (!isset($langCounts[$base])) {
            $langCounts[$base] = 0;
        }
        $langCounts[$base]++;
    }
    arsort($langCounts);
    $dominant = array_key_first($langCounts) ?? 'en';

    $result = [
        'title' => $title,
        'artist' => $artist,
        'language' => $dominant,
        'lang_counts' => $langCounts,
        'lyrics' => $processed,
    ];

    echo json_encode($result, JSON_UNESCAPED_UNICODE);
}

// ── Fetch lyrics from lyrics.ovh ───────────────────────────────────────────

function fetchLyrics($artist, $title) {
    $url = 'https://api.lyrics.ovh/v1/' . urlencode($artist) . '/' . urlencode($title);

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 15,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_SSL_VERIFYPEER => true,
    ]);
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpCode !== 200) return null;

    $data = json_decode($response, true);
    return $data['lyrics'] ?? null;
}

// ── Clean lyrics ───────────────────────────────────────────────────────────

function cleanLyrics($raw) {
    $lines = [];
    foreach (explode("\n", $raw) as $line) {
        $line = trim($line);
        if (!$line) continue;
        if (preg_match('/^\[.*\]$/', $line)) continue;
        $lines[] = $line;
    }
    return $lines;
}

// ── Process with OpenAI (parallel via curl_multi) ──────────────────────────

function processWithOpenAI($lines) {
    // Split into chunks
    $chunks = array_chunk($lines, CHUNK_SIZE);

    if (count($chunks) === 1) {
        return callOpenAIChunk($chunks[0]);
    }

    // Parallel requests with curl_multi
    $multiHandle = curl_multi_init();
    $handles = [];

    foreach ($chunks as $i => $chunk) {
        $ch = buildOpenAICurl($chunk);
        curl_multi_add_handle($multiHandle, $ch);
        $handles[$i] = $ch;
    }

    // Execute all in parallel
    $running = null;
    do {
        curl_multi_exec($multiHandle, $running);
        curl_multi_select($multiHandle);
    } while ($running > 0);

    // Collect results in order
    $allLines = [];
    foreach ($handles as $i => $ch) {
        $response = curl_multi_getcontent($ch);
        curl_multi_remove_handle($multiHandle, $ch);
        curl_close($ch);

        $data = json_decode($response, true);
        $content = $data['choices'][0]['message']['content'] ?? '{}';
        $parsed = json_decode($content, true);
        $chunkLines = $parsed['lyrics'] ?? [];
        $allLines = array_merge($allLines, $chunkLines);
    }

    curl_multi_close($multiHandle);
    return $allLines;
}

function callOpenAIChunk($lines) {
    $ch = buildOpenAICurl($lines);
    $response = curl_exec($ch);
    curl_close($ch);

    $data = json_decode($response, true);
    $content = $data['choices'][0]['message']['content'] ?? '{}';
    $parsed = json_decode($content, true);
    return $parsed['lyrics'] ?? [];
}

function buildOpenAICurl($lines) {
    $lyricsText = implode("\n", $lines);

    $prompt = "Tu es un expert en musique internationale et en linguistique.\n\n"
        . "Pour chaque ligne de paroles ci-dessous :\n"
        . "1. Detecte la VRAIE langue (ko, ja, en, hi, pa, es, fr, ar, zh, ou autre code ISO 639-1). ATTENTION: du texte en alphabet latin peut etre du pendjabi romanisé, du hindi romanisé, de l'espagnol, etc. Ne classe PAS automatiquement tout texte latin comme \"en\". Analyse le vocabulaire et la grammaire pour identifier la vraie langue.\n"
        . "2. Si la ligne contient un mélange de langues, utilise le suffixe \"-mixed\" (ex: \"ko-mixed\", \"pa-mixed\")\n"
        . "3. Donne la romanisation si la ligne contient des caractères non-latins (coréen, japonais, chinois, arabe, etc.). Si la ligne est DEJA en alphabet latin, romanized = la ligne elle-meme.\n"
        . "4. Traduis TOUJOURS en français, quelle que soit la langue source. Meme si la ligne est en anglais, traduis-la.\n\n"
        . "Reponds UNIQUEMENT en JSON valide avec cette structure exacte :\n"
        . "{\"lyrics\": [{\"line\": \"texte original\", \"language\": \"code_langue\", \"romanized\": \"romanisation\", \"translation\": \"traduction française\"}]}\n\n"
        . "- Utilise la romanisation révisée pour le coréen, Hepburn pour le japonais\n"
        . "- La traduction doit TOUJOURS etre presente et en français, jamais null\n\n"
        . "PAROLES :\n" . $lyricsText;

    $payload = json_encode([
        'model' => 'gpt-4o-mini',
        'messages' => [
            ['role' => 'system', 'content' => 'Tu es un assistant expert en linguistique et traduction musicale. Tu detectes avec precision la langue reelle des paroles, y compris les langues ecrites en alphabet latin comme le pendjabi romanise, le hindi romanise, l\'espagnol, etc. Tu reponds uniquement en JSON valide.'],
            ['role' => 'user', 'content' => $prompt],
        ],
        'temperature' => 0.3,
        'response_format' => ['type' => 'json_object'],
    ], JSON_UNESCAPED_UNICODE);

    $ch = curl_init('https://api.openai.com/v1/chat/completions');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_TIMEOUT => 60,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . OPENAI_KEY,
        ],
        CURLOPT_SSL_VERIFYPEER => true,
    ]);

    return $ch;
}
