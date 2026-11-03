param(
    [string]$SerialPort='COM5',
    [int]$SerialBaud=115200,
    [switch]$EmptyGripperConfirmed,
    [switch]$Move,
    [switch]$ObserveResidualsOnly,
    [string]$OutputRoot
)
# Reviewed reboot envelope -> accepted low HOME. Never an arbitrary loaded return.
$ErrorActionPreference='Stop'
$pickupProject=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if($Move -and -not $EmptyGripperConfirmed){throw 'Fresh empty-gripper confirmation is required after reboot; no motion.'}
if(-not $OutputRoot){$OutputRoot=Join-Path $pickupProject 'artifacts\phase3c\mode_b_ttl_20261028\restart_trials'}
$pickupRun=Join-Path $OutputRoot ([DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($pickupRun)
$pickupLog=Join-Path $pickupRun 'TTL_HOME_RESULT.json'
$pickupPython=Join-Path $pickupProject 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
$pickupHelper=Join-Path $PSScriptRoot 'prepare_low_home.py'
$pickupSerialPort=$SerialPort;$pickupSerialBaud=$SerialBaud
$pickupObserveResidualsOnly=[bool]$ObserveResidualsOnly
$pickupJournal=[ordered]@{
    schema='gesture.mode_b.ttl_startup_home_result.v1';status='STARTED';motion_requests=0
    transport='TTL_SERIAL';serial_port=$SerialPort;observations=@();requests=@()
    operator_confirmed_empty=[bool]$EmptyGripperConfirmed;error=$null
    firmware_boot_home_changed=$false;general_mapping_calibrated=$false
    residual_observations=@();residual_stop_enabled=(-not [bool]$ObserveResidualsOnly)
}
. (Join-Path $PSScriptRoot 'mode_b_native_stream.ps1')
. (Join-Path $PSScriptRoot 'mode_b_serial_stream.ps1')
Save-PickupJournal
try{
    $pre=Read-PickupFeedback -Label TTL_RESTART_PRE
    $planDir=Join-Path $pickupRun 'plan'
    & $pickupPython -B -X utf8 $pickupHelper --capture $pre.Path --output $planDir --accepted-home | Out-Host
    if($LASTEXITCODE -ne 0){throw 'Startup-to-HOME model check failed; no motion.'}
    $planPath=Join-Path $planDir 'LOW_HOME_PLAN.json'
    $model=([IO.File]::ReadAllText($planPath) -creplace '"T"\s*:', '"command_message_type":')|ConvertFrom-Json
    $pickupJournal['plan_file']=$planPath
    if(-not $Move){$pickupJournal.status='PREVIEW_ONLY_NO_MOTION';return}
    if(([DateTimeOffset]::UtcNow-[DateTimeOffset]::Parse($pre.Capture.captured_at_utc)).TotalSeconds -gt 25){throw 'Startup capture expired; no motion.'}
    $cmd=$model.native_command_once
    if($cmd.command_message_type -ne 122){throw 'Unexpected startup command.'}
    $wireBody=([ordered]@{b=$cmd.b;s=$cmd.s;e=$cmd.e;t=$cmd.t;r=$cmd.r;h=$cmd.h;spd=$cmd.spd;acc=$cmd.acc}|ConvertTo-Json -Compress)
    $wire='{"T":122,'+$wireBody.Substring(1)
    $native=[pscustomobject]@{
        phase='TTL_STARTUP_TO_ACCEPTED_LOW_HOME';start_firmware_rad=$model.start_firmware_rad
        arrival_tolerance_deg=$model.arrival_tolerance_deg
        stage=[pscustomobject]@{native_wire_json=$wire;target_firmware_rad=$model.target_firmware_rad}
    }
    Invoke-PickupStream -Plan $native
    if($ObserveResidualsOnly){
        # T122 is one asynchronous command: allow its programmed move to run
        # before starting the next segment, without requiring angular arrival.
        $maximumDelta=0.0
        foreach($name in @('b','s','e','t','r','g')){
            $maximumDelta=[Math]::Max($maximumDelta,[Math]::Abs(([double]$model.target_firmware_rad.$name-[double]$model.start_firmware_rad.$name)*180/[Math]::PI))
        }
        Start-Sleep -Milliseconds ([int][Math]::Ceiling(1000*($maximumDelta/[double]$cmd.spd+2)))
    }
    $post=Wait-PickupArrival -Target $model.target_firmware_rad -Label TTL_LOW_HOME -Tolerances $model.arrival_tolerance_deg
    $pickupJournal.status='TTL_ACCEPTED_LOW_HOME_FEEDBACK_FINISHED_EMPTY'
    Write-Host 'LOW_HOME_FINISHED: ready for fresh camera localization. No grasp, transfer or release requested.'
}catch{
    $pickupJournal.status='STOPPED_NO_FURTHER_REQUESTS';$pickupJournal.error=$_.Exception.Message;throw
}finally{
    Save-PickupJournal
    Write-Host ('TTL_HOME_LOG: '+$pickupLog)
    Write-Host ('MOTION_REQUESTS: '+$pickupJournal.motion_requests)
}
