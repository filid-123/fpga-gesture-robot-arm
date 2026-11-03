param([switch]$CheckOnly,[switch]$RuntimeOnly,[switch]$Preview,[switch]$MonitorOnly,[string]$OutDir='', [int]$Port=8765,[double]$Seconds=0)
$ErrorActionPreference='Stop'
$taskPython=Join-Path $PSScriptRoot '.venv-ab-rocm/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {throw 'Run setup_mode_ab.ps1 first to install the Windows ROCm environment.'}
$taskArgs=@('-X','utf8','-B',(Join-Path $PSScriptRoot 'scripts/run_mode_ab.py'),'--port',"$Port")
if ($RuntimeOnly) {$taskArgs+='--runtime-only'}
if ($CheckOnly) {$taskArgs+='--check-only'} else {
    if (-not $OutDir) {$OutDir=Join-Path $PSScriptRoot ('runs/ab_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))}
    $taskArgs+=@('--out-dir',$OutDir)
    if ($Preview) {$taskArgs+='--preview'} else {$taskArgs+='--run'}
    if ($MonitorOnly) {$taskArgs+='--monitor-only'}
    $taskArgs+=@('--seconds',"$Seconds")
}
& $taskPython @taskArgs
exit $LASTEXITCODE
