param([string]$Output)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Add-Type -Path (Join-Path $taskRoot 'pc/native/RgbCameraControls.cs')
$taskDevices = @([Gesture.Rgb.CameraControls]::Inspect())
$taskReport = [ordered]@{
    schema = 'gesture.ai_pc.rgb_dshow_capabilities.v1'
    status = 'COMPLETED'
    hardware_settings_written = $false
    capability_flags = @{ auto = 1; manual = 2 }
    devices = $taskDevices
    note = 'DirectShow enumeration order must be checked visually before using a camera index.'
}
$taskJson = $taskReport | ConvertTo-Json -Depth 8
if ($Output) {
    $taskFullOutput = [System.IO.Path]::GetFullPath($Output)
    if (Test-Path -LiteralPath $taskFullOutput) { throw 'Output already exists.' }
    [System.IO.File]::WriteAllText($taskFullOutput, $taskJson, [System.Text.UTF8Encoding]::new($false))
}
Write-Output $taskJson
