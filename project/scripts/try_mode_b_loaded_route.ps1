param(
    [string]$Plan = 'artifacts\phase3c\mode_b_pc_trial_20261028\loaded_remaining_v1\LOADED_ROUTE_PLAN.json',
    [string]$Verification = 'artifacts\phase3c\mode_b_pc_trial_20261028\loaded_remaining_v1\COPPELIA_VERIFICATION.json',
    [switch]$Move,
    [switch]$ObserveResidualsOnly,
    [switch]$DirectPhysicalTrial,
    [ValidateRange(0,3)][int]$Selection=0,
    [string]$SerialPort,
    [int]$SerialBaud=115200,
    [string]$ArmAddress = '192.168.4.1'
)
$ErrorActionPreference='Stop'
$pickupProject=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
foreach ($name in @('Plan','Verification')) {
    $value=Get-Variable -Name $name -ValueOnly
    if (-not [IO.Path]::IsPathRooted($value)) { Set-Variable -Name $name -Value (Join-Path $pickupProject $value) }
}
$route=Get-Content -LiteralPath $Plan -Raw -Encoding UTF8 | ConvertFrom-Json
$sourceRegistration=$route.scope -eq 'TODAY_EMPIRICAL_HIGH_SOURCE_REGISTRATION'
$fullTrial=$route.scope -in @('FRESH_RED_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL','FRESH_CYLINDER_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL','FRESH_ERASER_LOCAL_TTL_COMPLETE_COMMISSIONING_TRIAL','TODAY_EMPIRICAL_OPEN_HIGH_TO_FULL_DELIVERY') -or $sourceRegistration
if([bool]$route.only_source_registration -ne $sourceRegistration){throw 'Source registration scope/flag mismatch; no motion.'}
if($sourceRegistration -and ($route.stages.Count -ne 1 -or $route.stages[0].phase -ne 'DIRECT_PREGRASP')){throw 'Source registration permits only the recorded high approach; no descent or transfer.'}
$pickupObserveResidualsOnly=[bool]$ObserveResidualsOnly
if($ObserveResidualsOnly -and -not $SerialPort){throw 'Residual-observation mode is restricted to the explicit TTL commissioning trial.'}
if ($route.filid_profile -and -not $SerialPort) {
    throw 'Filid continuation is a TTL review candidate with a different support height; this Wi-Fi entrance cannot execute it.'
}
if ($Move -and $route.filid_profile -and -not $route.support_height_physically_ready) {
    throw 'The150mm support is accepted but not placed; no release route can execute yet.'
}
if($DirectPhysicalTrial){
    if(-not $SerialPort -or -not $ObserveResidualsOnly -or $route.request.object_class -ne 'red_cube' -or $route.red_pickup_depth_correction.additional_descent_mm -ne 12){
        throw 'Direct physical entry is restricted to the explicitly requested red depth12 trial.'
    }
    $sim=[pscustomobject]@{route_sha256=(Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLowerInvariant()}
}else{
    $sim=Get-Content -LiteralPath $Verification -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $sim.passed -or $sim.route_sha256 -ne (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLowerInvariant()) {
        throw 'Matching native-route mesh verification required; no motion.'
    }
}
if ($route.schema -ne 'gesture.mode_b.loaded_continuation.v1' -or -not $route.offline_verification.passed) {
    throw 'Invalid checked loaded continuation; no motion.'
}
$accepted=Get-Content -LiteralPath $route.accepted_pickup_file -Raw -Encoding UTF8 | ConvertFrom-Json
if ($accepted.status -ne 'PICKUP_LIFT_OPERATOR_ACCEPTED_HOLDING_RED' -or
    (Get-FileHash -LiteralPath $route.accepted_pickup_file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $route.accepted_pickup_sha256) {
    throw 'Accepted pickup source changed; no motion.'
}
$pickupRun=Join-Path $pickupProject ('artifacts\phase3c\mode_b_pc_trial_20261028\loaded_route_trials\'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($pickupRun)
$pickupLog=Join-Path $pickupRun 'LOADED_ROUTE_RESULT.json'
$pickupPython=Join-Path $pickupProject 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
$pickupHelper=Join-Path $PSScriptRoot 'prepare_mode_b_loaded_route.py'
$pickupJournal=[ordered]@{
    schema='gesture.mode_b.loaded_route_result.v1';status='STARTED';motion_requests=0
    route_file=$Plan;route_sha256=$sim.route_sha256;object_class=$route.request.object_class;observations=@();requests=@();completed_stages=@()
    current_payload=$(if($route.scope -eq 'TODAY_EMPIRICAL_OPEN_HIGH_TO_FULL_DELIVERY'){'EMPTY_OPEN_HIGH_OPERATOR_OBSERVED'}elseif($fullTrial){'EMPTY_OPERATOR_CONFIRMED_AFTER_REBOOT'}else{'RED_CUBE_30MM'});release_requested=$false;release_observed=$false
    physical_general_mapping_calibrated=$false;physical_delivery_confirmed=$false;error=$null
    direct_physical_trial_by_operator_request=[bool]$DirectPhysicalTrial;mesh_verification_performed=(-not [bool]$DirectPhysicalTrial)
    residual_observations=@();residual_stop_enabled=(-not [bool]$ObserveResidualsOnly)
    live_model_geometry_policy=$(if($ObserveResidualsOnly){'POSTRUN_DIAGNOSTIC_ONLY_OFFLINE_MESH_CHECK_REQUIRED'}else{'LIVE_CHECK'})
}
. (Join-Path $PSScriptRoot 'mode_b_native_stream.ps1')
if($SerialPort){
    $pickupSerialPort=$SerialPort;$pickupSerialBaud=$SerialBaud
    . (Join-Path $PSScriptRoot 'mode_b_serial_stream.ps1')
    $pickupJournal['transport']='TTL_SERIAL';$pickupJournal['serial_port']=$SerialPort
}
function Send-RouteEvent {
    param([string]$Label,[string]$Wire)
    $entry=[ordered]@{label=$Label;wire_json=$Wire;attempted_utc=[DateTimeOffset]::UtcNow.ToString('o');response=$null}
    $pickupJournal.requests+=$entry;$pickupJournal.motion_requests++;$pickupJournal.status=$Label+'_REQUEST_ATTEMPTED_ONCE'
    if ($Label -eq 'RELEASE') { $pickupJournal.release_requested=$true;$pickupJournal.current_payload='RELEASE_REQUESTED_PHYSICAL_RESULT_UNKNOWN' }
    Save-PickupJournal
    $entry.response=Send-PickupWire -Wire $Wire
    Save-PickupJournal
    if($pickupObserveResidualsOnly){
        $eventCommand=$Wire|ConvertFrom-Json
        if($eventCommand.T -eq 106){
            $startHand=[double]$pickupJournal.final_firmware_rad.g
            $dwell=[Math]::Abs([double]$eventCommand.cmd-$startHand)*4096/(2*[Math]::PI)/[double]$eventCommand.spd+1
            Write-Host ('GRIPPER_SCHEDULED_DWELL_SECONDS: {0:F2}; no residual gate.' -f $dwell)
            Start-Sleep -Milliseconds ([int][Math]::Ceiling(1000*$dwell))
        }
    }
}
function Check-ReleaseGeometry {
    param($Capture)
    $checkPath=Join-Path $pickupRun 'ACTUAL_RELEASE_GEOMETRY.json'
    $code=@'
import json,sys,numpy as np
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'scripts'))
from prepare_mode_b_loaded_route import read,observed,objects,geometry_check,write,FLIP,payload_half_extents
p=read(sys.argv[1]);q=observed(read(sys.argv[2]));r,w=objects(p)
result=geometry_check(p,q,True,cached=(r,w));T=r.fk(np.r_[q[:5],0.])@r.payload_attachment
half=payload_half_extents(p,T)[:2];support=np.array(p['request']['destination']['support_centre_mm'])
offset=np.abs(T[:2,3]-support[:2]);margin=np.array(p['request']['destination']['size_xy_mm'])/2-half-offset
result['support_footprint_margin_mm']=margin.tolist()
result['passed']=bool(margin.min()>=2 and support[2]+.5<=result['object_bottom_mm']<=support[2]+20)
result['scope']='LOCALLY_ANCHORED_MODEL_FROM_FRESH_JOINTS_NOT_PHYSICAL_PLACEMENT_PROOF'
write(sys.argv[3],result)
print(json.dumps(result));sys.exit(0 if result['passed'] else 1)
'@
    Push-Location -LiteralPath $pickupProject
    try { $code | & $pickupPython -B -X utf8 - $Plan $Capture.Path $checkPath | Out-Host } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Fresh release footprint/height check failed; gripper remains closed.' }
    $pickupJournal.release_geometry=$checkPath;Save-PickupJournal
}
Save-PickupJournal
try {
    $pre=Read-PickupFeedback -Label LOADED_ROUTE_PRE
    foreach ($name in @('b','s','e','t','r','g')) {
        $delta=[Math]::Abs(([double]$pre.Capture.samples[-1].joint_rad.$name-[double]$route.start_firmware_rad.$name)*180/[Math]::PI)
        if ($delta -gt 1 -and -not $ObserveResidualsOnly) { throw ('Loaded start changed at '+$name+'; no motion.') }
    }
    if (-not $Move) {
        $pickupJournal.status='PREVIEW_ONLY_NO_MOTION'
        Write-Host 'PREVIEW_ONLY: matching checked native route. No motion.'
        return
    }
    foreach ($stage in $route.stages) {
        $stage | Add-Member -NotePropertyName loaded_route_geometry_plan -NotePropertyValue $Plan -Force
        Invoke-PickupStream -Plan $stage
        $post=Wait-PickupArrival -Target $stage.stage.target_firmware_rad -Label $stage.phase -Tolerances $stage.arrival_tolerance_deg
        $pickupJournal.completed_stages+=@($stage.phase);Save-PickupJournal
        if($fullTrial -and $stage.phase -eq 'DIRECT_PREGRASP'){
            Send-RouteEvent -Label OPEN_HIGH -Wire $route.open_before_descent_wire_json
            $target=$post.Capture.samples[-1].joint_rad|ConvertTo-Json|ConvertFrom-Json
            $target.g=[double]($route.open_before_descent_wire_json|ConvertFrom-Json).cmd
            $post=Wait-PickupArrival -Target $target -Label OPEN_HIGH -Tolerances $route.arrival_tolerance_deg
            if($sourceRegistration){
                $pickupJournal.status='TODAY_SUCCESSFUL_HIGH_OPEN_PHYSICAL_SOURCE_OFFSET_REQUIRED'
                $pickupJournal.current_payload='EMPTY_OPEN_HIGH_WAITING_FOR_SOURCE_REGISTRATION'
                Write-Host 'HIGH_ONLY_FINISHED: recorded successful high pose and open hand; no descent, closure, transfer or automatic HOME.'
                return
            }
        }
        if($fullTrial -and $stage.phase -eq 'DESCEND'){
            Send-RouteEvent -Label CLOSE_SOURCE -Wire $route.close_after_descent_wire_json
            $target=$post.Capture.samples[-1].joint_rad|ConvertTo-Json|ConvertFrom-Json
            $target.g=[double]($route.close_after_descent_wire_json|ConvertFrom-Json).cmd
            $post=Wait-PickupArrival -Target $target -Label CLOSE_SOURCE -Tolerances $route.arrival_tolerance_deg
            # Freeze the raw visual source and actual closing observation now;
            # later detections and compensation must not replace the return origin.
            $pickupJournal['grasp_origin_observation']=[ordered]@{
                source_pickup=$route.request.pickup;object_class=$route.request.object_class
                close_feedback_file=$post.Path
                close_feedback_sha256=(Get-FileHash -LiteralPath $post.Path -Algorithm SHA256).Hash.ToLowerInvariant()
                observed_firmware_rad=$post.Capture.samples[-1].joint_rad
                descent_target_firmware_rad=$stage.stage.target_firmware_rad
            }
            $pickupJournal.current_payload='CLOSURE_FEEDBACK_ESTABLISHED_PHYSICAL_GRIP_UNCONFIRMED'
            Save-PickupJournal
        }
        if($fullTrial -and $stage.phase -eq 'LIFT'){
            $pickupJournal.current_payload='LIFT_FEEDBACK_FINISHED_PHYSICAL_GRIP_UNCONFIRMED'
            Save-PickupJournal
        }
        if($route.pc_confirm_delivery -and $stage.phase -eq 'PREPLACE'){
            $pickupJournal['confirmation_source']='USER_AUTHORIZED_PC_FIXED_SUPPORT_TRIAL_NO_FPGA_GESTURE_INPUT'
            Save-PickupJournal
            Start-Sleep -Milliseconds 2500
        }
        if ($stage.phase -eq 'PLACE') {
            if($ObserveResidualsOnly){
                $pickupJournal['release_geometry_policy']='OFFLINE_CHECKED; LIVE_RESIDUALS_OBSERVED_ONLY_BY_USER_REQUEST'
                Save-PickupJournal
            }else{Check-ReleaseGeometry -Capture $post}
            Send-RouteEvent -Label RELEASE -Wire $route.release_wire_json
            $target=$post.Capture.samples[-1].joint_rad | ConvertTo-Json | ConvertFrom-Json
            $target.g=[double]($route.release_wire_json|ConvertFrom-Json).cmd
            $release=Wait-PickupArrival -Target $target -Label RELEASE -Tolerances $route.arrival_tolerance_deg
            $pickupJournal.release_observed=$true;$pickupJournal.current_payload='HAND_OPEN_PHYSICAL_RELEASE_REVIEW_REQUIRED'
            Save-PickupJournal
        }
    }
    if($route.only_holding_recovery){
        $pickupJournal.status='TTL_LOADED_ESCAPE_FEEDBACK_FINISHED_HOLDING_RED'
        $pickupJournal.current_payload='RED_CUBE_30MM'
        Write-Host 'HOLDING_CLEAR: no opening, release or HOME requested. New fixture is not yet placed.'
        return
    }
    Send-RouteEvent -Label PARK_CLOSE -Wire $route.park_close_wire_json
    $target=$post.Capture.samples[-1].joint_rad | ConvertTo-Json | ConvertFrom-Json
    $target.g=3.10
    $park=Wait-PickupArrival -Target $target -Label PARK_CLOSE -Tolerances $route.arrival_tolerance_deg
    $pickupJournal.status='DELIVERY_RELEASE_AND_LOW_HOME_FEEDBACK_FINISHED_PHYSICAL_REVIEW_REQUIRED'
    Write-Host 'FINISHED: release and low HOME feedback completed. Observe actual object placement and empty HOME.'
} catch {
    $pickupJournal.status='STOPPED_NO_FURTHER_REQUESTS';$pickupJournal.error=$_.Exception.Message
    throw
} finally {
    Save-PickupJournal
    if($fullTrial -and -not $sourceRegistration -and $pickupJournal.status -eq 'DELIVERY_RELEASE_AND_LOW_HOME_FEEDBACK_FINISHED_PHYSICAL_REVIEW_REQUIRED'){
        $originFile=Join-Path $pickupRun 'GRASP_ORIGIN.json'
        $originSelection=$Selection
        if($originSelection -eq 0){$originSelection=if($route.request.object_class -eq 'eraser'){2}elseif($route.request.object_class -eq 'small_canister'){3}else{1}}
        & $pickupPython -B -X utf8 (Join-Path $PSScriptRoot 'prepare_mode_b_restock.py') record `
            --delivery-plan $Plan --delivery-result $pickupLog --selection $originSelection --output $originFile | Out-Host
        if($LASTEXITCODE -ne 0){Write-Warning 'Delivery finished, but return-origin export failed; do not start automatic restock with an unbound origin.'}
        else{Write-Host ('GRASP_ORIGIN: '+$originFile)}
    }
    Write-Host ('LOADED_ROUTE_LOG: '+$pickupLog)
    Write-Host ('MOTION_REQUESTS: '+$pickupJournal.motion_requests)
}
