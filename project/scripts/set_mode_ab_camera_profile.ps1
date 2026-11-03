param([Parameter(Mandatory=$true)][string]$DevicePath,
      [ValidateSet('exposure','white_balance','gain','brightness')][string]$Property,
      [Parameter(Mandatory=$true)][int]$Value,
      [ValidateSet(1,2)][int]$Flags)
$ErrorActionPreference='Stop'
try {
    Add-Type -Path (Join-Path (Split-Path -Parent $PSScriptRoot) 'pc/mode_ab/native/RgbCameraProfile.cs')
    $taskId=@{exposure=4;white_balance=7;gain=9;brightness=0}[$Property]
    $taskResult=[Gesture.ModeAbRgb.CameraControls]::SetProperty($DevicePath,$taskId,($Property -ne 'exposure'),$Value,$Flags)
    $taskResult | ConvertTo-Json -Depth 6
    if (-not $taskResult.ReadbackMatched) { exit 2 }
} catch {
    @{status='ERROR';error=$_.Exception.Message} | ConvertTo-Json
    exit 2
}
