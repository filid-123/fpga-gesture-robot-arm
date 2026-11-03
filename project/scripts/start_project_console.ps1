param(
    [int]$Port = 8765,
    [string]$Config
)
$ErrorActionPreference = 'Stop'
$consoleRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$consolePython = Join-Path $consoleRoot '.venv-multiobject\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $consolePython)) {
    $consolePython = Join-Path $consoleRoot 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $consolePython)) {
    $consolePython = (Get-Command python -ErrorAction Stop).Source
}
$consoleArgs = @('-B', '-X', 'utf8', (Join-Path $consoleRoot 'web\project-console\server.py'), '--port', "$Port")
if ($Config) {
    $consoleArgs += @('--config', (Resolve-Path -LiteralPath $Config).Path)
}
& $consolePython @consoleArgs
