param(
    [Parameter(Mandatory=$true)][string]$Plan,
    [Parameter(Mandatory=$true)][string]$Verification,
    [string]$SerialPort='COM5',
    [switch]$Move,
    [switch]$EmptyGripperConfirmed,
    [switch]$HeldObjectConfirmed,
    [switch]$StoppedPoseConfirmed,
    [switch]$PublicAreaClearConfirmed,
    [switch]$OriginalSourceVacantConfirmed,
    [switch]$PublicObjectPlacementConfirmed,
    [switch]$StrictResidualStops
)
# Preview is entirely offline. This entry never runs the camera or FPGA.
$ErrorActionPreference='Stop'
$pickupProject=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pickupPython=Join-Path $pickupProject 'artifacts\mode_b_motion_runtime\.venv\Scripts\python.exe'
$pickupHelper=Join-Path $PSScriptRoot 'prepare_mode_b_restock.py'
foreach($name in @('Plan','Verification')){
    $value=Get-Variable -Name $name -ValueOnly
    if(-not [IO.Path]::IsPathRooted($value)){Set-Variable -Name $name -Value (Join-Path $pickupProject $value)}
}
& $pickupPython -B -X utf8 $pickupHelper check --plan $Plan | Out-Host
if($LASTEXITCODE -ne 0){throw 'Restock origin/plan screening failed; no hardware access.'}
$route=Get-Content -LiteralPath $Plan -Raw -Encoding UTF8|ConvertFrom-Json
$sim=Get-Content -LiteralPath $Verification -Raw -Encoding UTF8|ConvertFrom-Json
if(-not $sim.passed -or $sim.route_sha256 -ne (Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash.ToLowerInvariant()){
    throw 'Matching restock mesh verification required; no hardware access.'
}
if(-not $Move){
    Write-Host ('OFFLINE_RESTOCK_READY: '+$route.task_kind+'; original return='+($route.return_centre_mm -join ','))
    Write-Host 'No serial/camera/FPGA access. Public pickup still requires physical validation.'
    return
}
if($StrictResidualStops){throw 'Strict live restock geometry is not yet supported; no hardware access. Use the checked supervised residual-observation entry.'}
$cancel=$route.task_kind -in @('RESTOCK_CANCEL','RESTOCK_CANCEL_EMPTY')
if(-not $PublicAreaClearConfirmed){throw 'The150mm fixture overlaps public pickup. Clear the public point and route before restock.'}
if($cancel){
    if(-not $StoppedPoseConfirmed){throw 'Cancellation continuation requires a confirmed stopped matching pose.'}
    if($route.task_kind -eq 'RESTOCK_CANCEL_EMPTY'){
        if(-not $EmptyGripperConfirmed){throw 'Empty cancellation requires confirmed empty gripper.'}
    }elseif(-not $HeldObjectConfirmed){throw 'Holding cancellation requires a confirmed held object.'}
}else{
    if(-not $EmptyGripperConfirmed -or -not $OriginalSourceVacantConfirmed -or -not $PublicObjectPlacementConfirmed){
        throw 'Confirm empty HOME, vacant original source and correctly placed public object before motion.'
    }
}
$pickupRun=Join-Path $pickupProject ('artifacts\phase3c\mode_b_return_20261029\runs\'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($pickupRun)
$pickupLog=Join-Path $pickupRun 'RESTOCK_RESULT.json'
$pickupSerialPort=$SerialPort;$pickupSerialBaud=115200
$pickupObserveResidualsOnly=(-not [bool]$StrictResidualStops)
$pickupJournal=[ordered]@{
    schema='gesture.mode_b.restock_result.v1';status='STARTED';task_kind=$route.task_kind
    route_file=$Plan;route_sha256=$sim.route_sha256;origin_record_file=$route.origin_record_file
    origin_record_sha256=$route.origin_record_sha256;object_class=$route.request.object_class
    return_centre_mm=$route.return_centre_mm;motion_requests=0;requests=@();observations=@();completed_stages=@()
    residual_observations=@();release_requested=$false;release_observed=$false;inventory_restored=$false
    physical_restock_confirmed=$false;current_payload=$(if($route.task_kind -eq 'RESTOCK_CANCEL'){'HELD_OPERATOR_CONFIRMED'}else{'EMPTY_OPERATOR_CONFIRMED'})
    error=$null;transport='TTL_SERIAL';serial_port=$SerialPort;residual_stop_enabled=[bool]$StrictResidualStops
}
. (Join-Path $PSScriptRoot 'mode_b_native_stream.ps1')
. (Join-Path $PSScriptRoot 'mode_b_serial_stream.ps1')
function Send-RestockEvent($Event){
    $entry=[ordered]@{label=$Event.label;wire_json=$Event.wire_json;attempted_utc=[DateTimeOffset]::UtcNow.ToString('o');response=$null}
    $pickupJournal.requests+=$entry;$pickupJournal.motion_requests++
    if($Event.label -like 'RELEASE_*'){$pickupJournal.release_requested=$true}
    Save-PickupJournal
    $entry.response=Send-PickupWire -Wire $Event.wire_json
    Save-PickupJournal
    $command=$Event.wire_json|ConvertFrom-Json
    $startHand=[double]$pickupJournal.final_firmware_rad.g
    $dwell=[Math]::Abs([double]$command.cmd-$startHand)*4096/(2*[Math]::PI)/[double]$command.spd+1
    Start-Sleep -Milliseconds ([int][Math]::Ceiling(1000*$dwell))
    $target=$pickupJournal.final_firmware_rad|ConvertTo-Json|ConvertFrom-Json
    $target.g=[double]$command.cmd
    $post=Wait-PickupArrival -Target $target -Label $Event.label -Tolerances $route.arrival_tolerance_deg
    if($Event.label -like 'RELEASE_*'){$pickupJournal.release_observed=$true;$pickupJournal.current_payload='RELEASE_FEEDBACK_OBSERVED_PHYSICAL_REVIEW_REQUIRED'}
    return $post
}
Save-PickupJournal
try{
    $pre=Read-PickupFeedback -Label RESTOCK_PRE
    $pickupJournal['final_firmware_rad']=$pre.Capture.samples[-1].joint_rad
    foreach($name in @('b','s','e','t','r','g')){
        if([double]$pre.Capture.observed_joint_range_deg.$name -gt .5){throw 'Restock entry is still moving; no motion sent.'}
        $delta=[Math]::Abs(([double]$pickupJournal.final_firmware_rad.$name-[double]$route.start_firmware_rad.$name)*180/[Math]::PI)
        if($delta -gt [double]$route.arrival_tolerance_deg.$name){throw ('Restock start differs at '+$name+'; no motion.')}
    }
    if($route.initial_event){$post=Send-RestockEvent $route.initial_event}
    foreach($stage in $route.stages){
        # Observe-only retains firmware/torque/communication checks in the TTL
        # transport. Strict mode adds model checks against the restock payload.
        Invoke-PickupStream -Plan $stage
        $post=Wait-PickupArrival -Target $stage.stage.target_firmware_rad -Label $stage.phase -Tolerances $stage.arrival_tolerance_deg
        $pickupJournal.completed_stages+=@($stage.phase);Save-PickupJournal
        $event=$route.event_after_stage.PSObject.Properties[$stage.phase]
        if($event){$post=Send-RestockEvent $event.Value}
    }
    $post=Send-RestockEvent $route.final_event
    $pickupJournal.inventory_restored=(-not $cancel)
    $pickupJournal.status=if($cancel){'RESTOCK_CANCEL_PUBLIC_RETURN_AND_HOME_SEQUENCE_FINISHED'}else{'RESTOCK_SOURCE_RELEASE_AND_HOME_SEQUENCE_FINISHED_PHYSICAL_REVIEW_REQUIRED'}
    Write-Host ('RESTOCK_FINISHED: inventory program-completion='+$pickupJournal.inventory_restored+'; actual placement requires operator feedback.')
}catch{
    $pickupJournal.status='STOPPED_NO_FURTHER_REQUESTS';$pickupJournal.error=$_.Exception.Message
    $pickupJournal.inventory_restored=$false
    throw
}finally{
    Save-PickupJournal
    Write-Host ('RESTOCK_RESULT: '+$pickupLog)
    Write-Host ('MOTION_REQUESTS: '+$pickupJournal.motion_requests)
}
