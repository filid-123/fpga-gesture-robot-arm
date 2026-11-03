param(
    [string]$SerialPort='COM5',
    [switch]$EmptyGripperConfirmed,
    [switch]$Move,
    [switch]$StrictResidualStops,
    [ValidateRange(0.1,3.0)][double]$SpeedMultiplier=3.0,
    [string]$OutputRoot
)
$ErrorActionPreference='Stop'
$call=@{SerialPort=$SerialPort;EmptyGripperConfirmed=[bool]$EmptyGripperConfirmed;
    Move=[bool]$Move;StrictResidualStops=[bool]$StrictResidualStops;
    SpeedMultiplier=$SpeedMultiplier;ObjectClass='eraser'}
if($OutputRoot){$call.OutputRoot=$OutputRoot}
& (Join-Path $PSScriptRoot 'run_mode_b_ttl_red_trial.ps1') @call
