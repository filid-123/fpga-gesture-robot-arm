param(
    [string]$SerialPort='COM5',
    [switch]$EmptyGripperConfirmed,
    [switch]$Move,
    [switch]$StrictResidualStops,
    [ValidateRange(0.1,3.0)][double]$SpeedMultiplier=2.0,
    [string]$OutputRoot
)
# Same checked HOME -> fresh camera -> plan -> simulation -> TTL workflow.
# Place one upright cylinder only, keeping camera/base/support unchanged.
$ErrorActionPreference='Stop'
$call=@{SerialPort=$SerialPort;EmptyGripperConfirmed=[bool]$EmptyGripperConfirmed;
    Move=[bool]$Move;StrictResidualStops=[bool]$StrictResidualStops;
    SpeedMultiplier=$SpeedMultiplier;ObjectClass='small_canister'}
if($OutputRoot){$call.OutputRoot=$OutputRoot}
& (Join-Path $PSScriptRoot 'run_mode_b_ttl_red_trial.ps1') @call
