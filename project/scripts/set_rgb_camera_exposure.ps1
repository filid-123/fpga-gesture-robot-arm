param(
    [Parameter(Mandatory=$true)][string]$DevicePath,
    [Parameter(Mandatory=$true)][int]$Exposure,
    [Parameter(Mandatory=$true)][ValidateSet(1, 2)][int]$Flags
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
try {
    Add-Type -Path (Join-Path $taskRoot 'pc/native/RgbCameraControls.cs')
    $taskResult = [Gesture.Rgb.CameraControls]::SetExposure($DevicePath, $Exposure, $Flags)
    $taskResult | ConvertTo-Json -Depth 6
    if (-not $taskResult.ReadbackMatched) { exit 2 }
} catch {
    @{ status = 'ERROR'; error = $_.Exception.Message } | ConvertTo-Json
    exit 2
}
