param(
    [string]$SerialPort='COM5',
    [switch]$EmptyGripperConfirmed,
    [switch]$Move,
    [switch]$StrictResidualStops,
    [switch]$SuccessfulHighOnly,
    [ValidateSet('red_cube','small_canister','eraser')][string]$ObjectClass='red_cube',
    [ValidateRange(0.1,3.0)][double]$SpeedMultiplier=3.0,
    [string]$OutputRoot
)
# Local red-cube commissioning: HOME -> fresh vision -> checked route -> TTL.
# This CPU/PC trial does not use FPGA gestures or accept general calibration.
$ErrorActionPreference='Stop'
$project=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if($Move -and -not $EmptyGripperConfirmed){throw 'Start this complete replay with an operator-confirmed empty gripper.'}
if($SuccessfulHighOnly -and $ObjectClass -ne 'red_cube'){throw 'Successful-high-only replay is a red reference diagnostic.'}
$localGraspProfile=Get-Content -LiteralPath (Join-Path $project 'config\ai_pc\mode_b_red_grasp_correction_20261028.json') -Raw -Encoding UTF8|ConvertFrom-Json
if($Move -and $localGraspProfile.coordinate_validation_pending){throw 'Desktop axes were found reversed. Finish the coordinate-only holdout check before another pickup.'}
if(-not $OutputRoot){$OutputRoot=Join-Path $project 'artifacts\phase3c\mode_b_ttl_20261028\complete_trials'}
$trial=Join-Path $OutputRoot ([DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($trial)
$log=Join-Path $trial 'COMPLETE_TRIAL.json'
$visionPython=Join-Path $project '.venv-multiobject\Scripts\python.exe'
$motionPython=Join-Path $project 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
$journal=[ordered]@{schema='gesture.mode_b.ttl_red_complete_pc_trial.v1';status='STARTED';serial_port=$SerialPort;
    operator_confirmed_empty=[bool]$EmptyGripperConfirmed;move=[bool]$Move;residual_stop_enabled=[bool]$StrictResidualStops;
    physical_grip_and_placement_accepted=$false;general_mapping_calibrated=$false;error=$null}
$journal['speed_multiplier']=$SpeedMultiplier
$journal['object_class']=$ObjectClass
$journal['successful_high_registration_only']=[bool]$SuccessfulHighOnly
$ownedSimulator=$null
function Save-CompleteTrial{$journal|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $log -Encoding UTF8}
function Require-TrialSuccess([string]$label){if($LASTEXITCODE -ne 0){throw ($label+' failed; earlier evidence retained.')}}
Save-CompleteTrial
Push-Location -LiteralPath $project
try{
    $captureRoot=Join-Path $trial 'home_check'
    & (Join-Path $PSScriptRoot 'collect_mode_b_serial_pose.ps1') -Port $SerialPort -PoseId COMPLETE_PRE -SampleCount 5 -OutputRoot $captureRoot
    $capture=(Get-ChildItem -LiteralPath $captureRoot -Filter POSE_CAPTURE.json -File -Recurse|Select-Object -First 1).FullName
    $current=Get-Content -LiteralPath $capture -Raw -Encoding UTF8|ConvertFrom-Json
    # PowerShell properties are case-insensitive; native T and joint t must
    # not share an object. Only the native message discriminator is renamed.
    $acceptedHome=([IO.File]::ReadAllText((Join-Path $project 'config\ai_pc\robot_home_current.json')) -creplace '"T"\s*:', '"command_message_type":')|ConvertFrom-Json
    $practical=Get-Content -LiteralPath config\ai_pc\mode_b_commissioning_tolerance_20261028.json -Raw -Encoding UTF8|ConvertFrom-Json
    $atHome=$true
    foreach($name in @('b','s','e','t','r','g')){
        if([Math]::Abs(([double]$current.samples[-1].joint_rad.$name-[double]$acceptedHome.firmware_joint_rad.$name)*180/[Math]::PI) -gt [double]$practical.arrival_tolerance_deg.$name){$atHome=$false}
    }
    if(-not $atHome){
        if(-not $Move){$journal.status='PREVIEW_REQUIRES_STARTUP_TO_HOME_ENTRY';return}
        & (Join-Path $PSScriptRoot 'try_mode_b_ttl_home.ps1') -SerialPort $SerialPort -EmptyGripperConfirmed -Move -ObserveResidualsOnly:(-not [bool]$StrictResidualStops) -OutputRoot (Join-Path $trial 'home_entry')
    }
    $raw=Join-Path $trial 'capture';$perception=Join-Path $trial 'perception';$metric=Join-Path $trial 'metric';$planDir=Join-Path $trial 'native_plan'
    & $visionPython -B -X utf8 artifacts\multiobject\six_objects_field_20261027\capture_camera_adjusted_check.py --out $raw --frames 3
    Require-TrialSuccess 'Raw camera capture'
    & $visionPython -B -X utf8 artifacts\multiobject\eraser_top_repair_20261027\evaluate_frozen_burst.py --capture $raw --out $perception --freeze artifacts\multiobject\eraser_top_repair_20261027\candidate_freeze_v2.json
    Require-TrialSuccess 'Frozen recognition'
    $metricArgs=@('--capture',$raw,'--perception',$perception,'--output',$metric)
    if($SuccessfulHighOnly){$metricArgs+='--successful-high-only'}
    $metricScript=if($ObjectClass -eq 'small_canister'){'scripts\prepare_mode_b_cylinder_restart.py'}elseif($ObjectClass -eq 'eraser'){'scripts\prepare_mode_b_eraser_restart.py'}else{'scripts\prepare_mode_b_red_restart.py'}
    & $visionPython -B -X utf8 $metricScript @metricArgs
    Require-TrialSuccess 'Local metric source'
    $poseRoot=Join-Path $trial 'fresh_home'
    & (Join-Path $PSScriptRoot 'collect_mode_b_serial_pose.ps1') -Port $SerialPort -PoseId PLAN_HOME -SampleCount 5 -OutputRoot $poseRoot
    $pose=(Get-ChildItem -LiteralPath $poseRoot -Filter POSE_CAPTURE.json -File -Recurse|Select-Object -First 1).FullName
    $plan=Join-Path $planDir 'LOADED_ROUTE_PLAN.json';$verification=Join-Path $planDir 'COPPELIA_VERIFICATION.json'
    $planner=if($SuccessfulHighOnly){'scripts\prepare_mode_b_successful_high.py'}else{'scripts\prepare_mode_b_ttl_full_trial.py'}
    & $motionPython -B -X utf8 $planner --capture $pose --request (Join-Path $metric 'request.json') --output $plan --speed-multiplier $SpeedMultiplier
    Require-TrialSuccess 'Native route planning'
    $listening=@(Get-NetTCPConnection -LocalPort 23020 -State Listen -ErrorAction SilentlyContinue)
    if(-not $listening.Count){
        $exe='C:\Program Files\CoppeliaRobotics\CoppeliaSimEdu\coppeliaSim.exe'
        $ownedSimulator=Start-Process -FilePath $exe -ArgumentList @('-h','-GzmqRemoteApi.rpcPort=23020') -WindowStyle Hidden -PassThru
        $ready=[Diagnostics.Stopwatch]::StartNew()
        while(-not @(Get-NetTCPConnection -LocalPort 23020 -State Listen -ErrorAction SilentlyContinue).Count){
            if($ready.Elapsed.TotalSeconds -gt 30){throw 'Dedicated simulator did not start'}
            Start-Sleep -Milliseconds 250
        }
    }
    & $motionPython -B -X utf8 sim\phase3_robot\verify_mode_b_loaded_route.py --plan $plan --output $verification --port 23020
    Require-TrialSuccess 'Native mesh simulation'
    $journal['plan_file']=$plan;$journal['verification_file']=$verification;Save-CompleteTrial
    $call=@{SerialPort=$SerialPort;Plan=$plan;Verification=$verification;Move=[bool]$Move;ObserveResidualsOnly=(-not [bool]$StrictResidualStops)}
    & (Join-Path $PSScriptRoot 'try_mode_b_loaded_route.ps1') @call
    $journal.status=if(-not $Move){'PREVIEW_CHECKED_NO_MOTION'}elseif($SuccessfulHighOnly){'TODAY_SUCCESSFUL_HIGH_REPLAYED_AWAITING_PHYSICAL_OFFSET'}else{'PC_TTL_SEQUENCE_FINISHED_PHYSICAL_REVIEW_REQUIRED'}
}catch{$journal.status='STOPPED_NO_FURTHER_REQUESTS';$journal.error=$_.Exception.Message;throw}
finally{
    Save-CompleteTrial
    if($ownedSimulator -and -not $ownedSimulator.HasExited){Stop-Process -Id $ownedSimulator.Id -ErrorAction SilentlyContinue}
    Pop-Location
    Write-Host ('COMPLETE_TRIAL_LOG: '+$log)
}
