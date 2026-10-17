<?php
/**
 * JSON proxy: CORS-enabled Nexus-Data JSON (whitelist only).
 *
 * $fileMap key order matches js/legit-builder/legit-builder.js `nexusFiles` (auto-load list).
 * Extra keys may appear at the end for files not yet in the client list.
 *
 * Note: `inv` is the hotfix override layer (loaded after inv4 in the client).
 *
 * Usage: LegitItems/nexus_data_proxy.php?file=<key>
 */

// Enable CORS - allow all origins (browsers still block file:// but this helps with web servers)
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Accept, Authorization, X-Requested-With');
header('Access-Control-Max-Age: 3600');
header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');

// Handle preflight OPTIONS request
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    header('Content-Length: 0');
    exit();
}

// Map file parameter to Nexus-Data JSON filenames (order = legit-builder.js nexusFiles; extras last).
$fileMap = [
    'inv0' => 'Nexus-Data-inv0.json',
    'inv4' => 'Nexus-Data-inv4.json',
    'inv' => 'Nexus-Data-inv.json',
    'inv6' => 'Nexus-Data-inv6.json',
    'inv_custom0' => 'Nexus-Data-inv_custom0.json',
    'inv_custom4' => 'Nexus-Data-inv_custom4.json',
    'inv_name_part0' => 'Nexus-Data-inv_name_part0.json',
    'inv_name_part4' => 'Nexus-Data-inv_name_part4.json',
    'inv_name_part6' => 'Nexus-Data-inv_name_part6.json',
    'inv_stat0' => 'Nexus-Data-inv_stat0.json',
    'inv_stat4' => 'Nexus-Data-inv_stat4.json',
    'ui_stat0' => 'Nexus-Data-ui_stat0.json',
    'ui_stat4' => 'Nexus-Data-ui_stat4.json',
    'ui_stat6' => 'Nexus-Data-ui_stat6.json',
    'ui_challenge_list0' => 'Nexus-Data-ui_challenge_list0.json',
    'attribute0' => 'Nexus-Data-attribute0.json',
    'attribute4' => 'Nexus-Data-attribute4.json',
    'attribute6' => 'Nexus-Data-attribute6.json',
    'gbx_ue_data_table0' => 'Nexus-Data-gbx_ue_data_table0.json',
    'gbx_ue_data_table4' => 'Nexus-Data-gbx_ue_data_table4.json',
    'gbx_ue_data_table6' => 'Nexus-Data-gbx_ue_data_table6.json',
    'itempool0' => 'Nexus-Data-itempool0.json',
    'itempool4' => 'Nexus-Data-itempool4.json',
    'itempool6' => 'Nexus-Data-itempool6.json',
    'itempoollist0' => 'Nexus-Data-ItemPoolList0.json',
    'itempoollist4' => 'Nexus-Data-ItemPoolList4.json',
    'itempoollist6' => 'Nexus-Data-ItemPoolList6.json',
    'skilltrees_data0' => 'Nexus-Data-skilltrees_data0.json',
    'skilltrees_data4' => 'Nexus-Data-skilltrees_data4.json',
    'skilltrees_data6' => 'Nexus-Data-skilltrees_data6.json',
    'uitooltipdata0' => 'Nexus-Data-uitooltipdata0.json',
    'uitooltipdata4' => 'Nexus-Data-uitooltipdata4.json',
    'uitooltipdata6' => 'Nexus-Data-uitooltipdata6.json',
    'resident0' => 'Nexus-Data-Resident0.json',
    'resident4' => 'Nexus-Data-Resident4.json',
    'resident6' => 'Nexus-Data-Resident6.json',
    'gbxactorpart0' => 'Nexus-Data-GbxActorPart0.json',
    'gbxactorpart4' => 'Nexus-Data-GbxActorPart4.json',
    'gbxactorpart6' => 'Nexus-Data-GbxActorPart6.json',
    'challenge0' => 'Nexus-Data-challenge0.json',
    'challenge4' => 'Nexus-Data-challenge4.json',
    'challenge6' => 'Nexus-Data-challenge6.json',
    'challenge_list0' => 'Nexus-Data-challenge_list0.json',
    'challenge_list4' => 'Nexus-Data-challenge_list4.json',
    'challenge_list6' => 'Nexus-Data-challenge_list6.json',
    'mission0' => 'Nexus-Data-Mission0.json',
    'mission4' => 'Nexus-Data-Mission4.json',
    'mission6' => 'Nexus-Data-Mission6.json',
    'missionset0' => 'Nexus-Data-missionset0.json',
    'missionset4' => 'Nexus-Data-missionset4.json',
    'missionset6' => 'Nexus-Data-missionset6.json',
    'gbx_discovery_location_meta_data4' => 'Nexus-Data-gbx_discovery_location_meta_data4.json',
    'gbx_discovery_location_meta_data6' => 'Nexus-Data-gbx_discovery_location_meta_data6.json',
    'game_region0' => 'Nexus-Data-game_region0.json',
    'game_region4' => 'Nexus-Data-game_region4.json',
    'game_region6' => 'Nexus-Data-game_region6.json',
    'progress_graph_group0' => 'Nexus-Data-progress_graph_group0.json',
    'progress_graph_group4' => 'Nexus-Data-progress_graph_group4.json',
    'progress_graph0' => 'Nexus-Data-progress_graph0.json',
    'progress_graph4' => 'Nexus-Data-progress_graph4.json',
    'progress_graph6' => 'Nexus-Data-progress_graph6.json',
    // Not yet in client nexusFiles; whitelist so deploys can serve it when added.
    'progress_graph_group6' => 'Nexus-Data-progress_graph_group6.json',
    'firmware4' => 'Nexus-Data-Firmware4.json',
    'firmware6' => 'Nexus-Data-Firmware6.json',
];
$examples = array_map(function ($key) {
    return "nexus_data_proxy.php?file={$key}";
}, array_keys($fileMap));

// Get the file parameter from query string (check $_GET first, then parse query string)
$fileParam = '';

// Try $_GET first (most common)
if (isset($_GET['file']) && !empty($_GET['file'])) {
    $fileParam = trim($_GET['file']);
}
// If not found, try parsing QUERY_STRING directly
elseif (isset($_SERVER['QUERY_STRING']) && !empty($_SERVER['QUERY_STRING'])) {
    parse_str($_SERVER['QUERY_STRING'], $queryParams);
    if (isset($queryParams['file']) && !empty($queryParams['file'])) {
        $fileParam = trim($queryParams['file']);
    }
}

// Validate file parameter
if (empty($fileParam)) {
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'Missing file parameter',
        'message' => 'You must specify which file to load (e.g., ?file=inv0, ?file=inv, ?file=itempool4)',
        'valid_files' => array_keys($fileMap),
        'examples' => $examples
    ]);
    exit();
}

// Allow only safe key characters (whitelist keys are [a-z0-9_]+)
if (!preg_match('/^[a-z0-9_]+$/', $fileParam)) {
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'Invalid file parameter',
        'received' => $fileParam,
        'message' => 'file must contain only lowercase letters, digits, and underscores',
        'valid_files' => array_keys($fileMap),
        'examples' => $examples
    ]);
    exit();
}

// Check if parameter value is valid
if (!isset($fileMap[$fileParam])) {
    http_response_code(400);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'Invalid file parameter',
        'received' => $fileParam,
        'valid_files' => array_keys($fileMap),
        'examples' => $examples
    ]);
    exit();
}

// Get the filename for this parameter
$filename = $fileMap[$fileParam];

// Resolve JSON file location (first hit wins).
// - This folder when the script lives under LegitItems/
// - Parent ../json (same layout as legit-builder same-origin json/ fallback)
// - ../LegitItems* when the script is deployed beside the app root
$parentDir = dirname(__DIR__);
$searchDirs = [
    __DIR__,
    __DIR__ . '/json',
    $parentDir . '/json',
    $parentDir,
    realpath(__DIR__ . '/../LegitItems'),
    realpath(__DIR__ . '/../LegitItems/json')
];
$filePath = null;
$resolvedDir = null;
foreach ($searchDirs as $dir) {
    if (!$dir) continue;
    $candidate = $dir . '/' . $filename;
    if (is_file($candidate) && is_readable($candidate)) {
        $filePath = $candidate;
        $resolvedDir = $dir;
        break;
    }
}

// Check if file exists in any known location
if ($filePath === null) {
    http_response_code(404);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'File not found',
        'expected_file' => $filename,
        'searched_directories' => array_values(array_filter($searchDirs))
    ]);
    exit();
}

// Read the file
$jsonContent = @file_get_contents($filePath);

if ($jsonContent === false) {
    $error = error_get_last();
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'Failed to read file',
        'file' => $filename,
        'resolved_directory' => $resolvedDir,
        'message' => $error ? $error['message'] : 'Unknown error'
    ]);
    exit();
}

// Validate JSON (avoid re-encoding: preserves bytes and saves memory on large dumps)
json_decode($jsonContent, true);
if (json_last_error() !== JSON_ERROR_NONE) {
    http_response_code(500);
    header('Content-Type: application/json');
    echo json_encode([
        'error' => 'Invalid JSON',
        'file' => $filename,
        'resolved_directory' => $resolvedDir,
        'message' => json_last_error_msg()
    ]);
    exit();
}

echo $jsonContent;

