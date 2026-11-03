param(
    [Parameter(Mandatory=$true)][string]$Session,
    [string]$SerialPort='COM5',
    [switch]$Move,
    [switch]$EmptyGripperConfirmed,
    [switch]$PublicAreaClearConfirmed,
    [switch]$OriginalSourceVacantConfirmed,
    [switch]$PublicObjectPlacementConfirmed
)
# Default is completely offline; this is a separate candidate entry.
$ErrorActionPreference='Stop'
$restockRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$restockPython=Join-Path $restockRoot 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
$engine=Join-Path $restockRoot 'pc\mode_b\RestockSerialSession.cs'
function Get-RestockHash([string]$Path){
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{return ([BitConverter]::ToString($algorithm.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-','').ToLowerInvariant()}
    finally{$algorithm.Dispose()}
}
$Session=(Resolve-Path -LiteralPath $Session).Path
$packet=Get-Content -LiteralPath $Session -Raw -Encoding UTF8|ConvertFrom-Json
if($packet.schema -ne 'gesture.mode_b.restock_serial_session.v1'){throw 'Wrong session schema; no hardware access.'}
foreach($pair in @(@($packet.plan_file,$packet.plan_sha256),@($packet.simulation_file,$packet.simulation_sha256),@($packet.acceptance_file,$packet.acceptance_sha256),@($engine,$packet.engine_sha256))){
    if((Get-RestockHash $pair[0]) -ne $pair[1]){throw 'Changed session dependency; no hardware access.'}
}
$restockCheck=Join-Path ([IO.Path]::GetTempPath()) ('restock_check_'+[guid]::NewGuid().ToString('N')+'.json')
try{
    & $restockPython -B -X utf8 (Join-Path $PSScriptRoot 'prepare_mode_b_restock_session.py') `
        --plan $packet.plan_file --verification $packet.simulation_file --acceptance $packet.acceptance_file --output $restockCheck | Out-Host
    if($LASTEXITCODE -ne 0 -or (Get-RestockHash $restockCheck) -ne (Get-RestockHash $Session)){throw 'Session differs from deterministic compiled plan; no hardware access.'}
}finally{
    if(Test-Path -LiteralPath $restockCheck){Remove-Item -LiteralPath $restockCheck}
}
if(-not $Move){Write-Host ('OFFLINE_SESSION_READY: '+$packet.requests+' exact original requests; persistent20ms TTL.');return}
if(-not $EmptyGripperConfirmed -or -not $PublicAreaClearConfirmed -or -not $OriginalSourceVacantConfirmed -or -not $PublicObjectPlacementConfirmed){
    throw 'Confirm empty HOME, public object placement, vacant original source and clear restock route before motion.'
}
Add-Type -Path $engine -ReferencedAssemblies @('System.dll','System.Web.Extensions.dll')
$restockRun=Join-Path $restockRoot ('artifacts\phase3c\mode_b_return_20261029\session_runs\'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($restockRun)
Copy-Item -LiteralPath $Session -Destination (Join-Path $restockRun 'SESSION.json')
$port=[ModeB.SerialRestockPort]::new($SerialPort)
$clock=[ModeB.RestockClock]::new()
$runner=[ModeB.RestockSerialSession]::new($port,$clock,$restockRun)
try{
    $runner.Run([IO.File]::ReadAllText($Session))
}finally{
    Write-Host ('RESTOCK_RESULT: '+(Join-Path $restockRun 'RESTOCK_RESULT.json'))
    Write-Host 'Software exit stops further requests; it is not a guaranteed physical emergency stop. No motion request is retried.'
}
