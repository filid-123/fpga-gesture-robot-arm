# Dot-source after mode_b_native_stream.ps1. Overrides transport, not planning.
function New-PickupSerial {
    $endpoint=[IO.Ports.SerialPort]::new($pickupSerialPort,$pickupSerialBaud,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $endpoint.Handshake=[IO.Ports.Handshake]::None;$endpoint.DtrEnable=$false;$endpoint.RtsEnable=$false
    $endpoint.NewLine="`n";$endpoint.ReadTimeout=100;$endpoint.WriteTimeout=1500
    $endpoint.Open();return $endpoint
}
function Send-PickupWire {
    param([string]$Wire)
    $endpoint=New-PickupSerial
    try { $endpoint.WriteLine($Wire);return 'TTL_WRITE_RETURNED_EXECUTION_NOT_ACKNOWLEDGED' }
    finally { $endpoint.Close();$endpoint.Dispose() }
}
function Read-PickupFeedback {
    param([string]$Label)
    $captureRoot=Join-Path $pickupRun $Label
    & (Join-Path $PSScriptRoot 'collect_mode_b_serial_pose.ps1') -Port $pickupSerialPort -Baud $pickupSerialBaud `
        -PoseId $Label -SampleCount 5 -TimeoutSeconds 15 -OutputRoot $captureRoot | Out-Host
    $files=@(Get-ChildItem -LiteralPath $captureRoot -Filter POSE_CAPTURE.json -File -Recurse)
    if ($files.Count -ne 1) { throw 'Expected one TTL capture.' }
    $capture=Get-Content -LiteralPath $files[0].FullName -Raw -Encoding UTF8|ConvertFrom-Json
    if ($capture.observation_status -ne 'CAPTURE_COMPLETE_NOT_VALIDATED') { throw 'Incomplete TTL feedback.' }
    foreach($sample in $capture.samples) {
        if($sample.feedback.Stalltor -or $sample.feedback.Stalltep -or $sample.feedback.Stallvol){throw 'Firmware fault.'}
    }
    $pickupJournal.observations+=$files[0].FullName;Save-PickupJournal
    return [pscustomobject]@{Path=$files[0].FullName;Capture=$capture}
}
function Invoke-PickupStream {
    param($Plan)
    . (Join-Path $PSScriptRoot 'roarm_state_json.ps1')
    $endpoint=$null;$process=$null
    $feedbackState=@{pending='';latest=$null;received=[DateTimeOffset]::MinValue}
    $timer=[Diagnostics.Stopwatch]::StartNew();$lastSave=-1000.0;$lastQuery=-1000.0;$frameIndex=0;$geometrySignature=$null
    $feedbackLog=Join-Path $pickupRun ($Plan.phase+'_TTL_FEEDBACK.jsonl')
    function Read-SerialAvailable {
        $part=$endpoint.ReadExisting()
        if($part){$feedbackState.pending+=$part}
        if($feedbackState.pending.Length -gt 1048576){throw 'Oversize TTL frame.'}
        while($feedbackState.pending.Contains("`n")) {
            $split=$feedbackState.pending.IndexOf("`n")
            $raw=$feedbackState.pending.Substring(0,$split).Trim();$feedbackState.pending=$feedbackState.pending.Substring($split+1)
            $f=ConvertFrom-RoArmStateJson -RawJson $raw
            if($null -eq $f){continue}
            if($f.Stalltor -or $f.Stalltep -or $f.Stallvol){throw 'TTL firmware fault; no following sample.'}
            foreach($name in @('torswitchB','torswitchS','torswitchE','torswitchT','torswitchR','torswitchG')){
                if($null -ne $f.$name -and [int]$f.$name -ne 1){throw 'Joint torque disabled.'}
            }
            $feedbackState.latest=$f;$feedbackState.received=[DateTimeOffset]::UtcNow
            Add-Content -LiteralPath $feedbackLog -Value $raw -Encoding UTF8
        }
    }
    try {
        $endpoint=New-PickupSerial
        $endpoint.WriteLine('{"T":105}')
        while($null -eq $feedbackState.latest -and $timer.Elapsed.TotalSeconds -lt 4){Read-SerialAvailable;Start-Sleep -Milliseconds 5}
        if($null -eq $feedbackState.latest){throw 'No current TTL feedback; no motion.'}
        foreach($name in @('b','s','e','t','r','g')){
            $limit=if($Plan.loaded_route_geometry_plan){[double]$Plan.arrival_tolerance_deg.$name}else{.5}
            if([Math]::Abs(([double]$feedbackState.latest.$name-[double]$Plan.start_firmware_rad.$name)*180/[Math]::PI) -gt $limit -and -not $pickupObserveResidualsOnly){throw ('TTL start mismatch '+$name)}
        }
        if($Plan.stage.native_wire_json){
            $entry=[ordered]@{label=$Plan.phase;wire_json=$Plan.stage.native_wire_json;attempted_utc=[DateTimeOffset]::UtcNow.ToString('o');response=$null}
            $pickupJournal.requests+=$entry;$pickupJournal.motion_requests++;Save-PickupJournal
            $endpoint.WriteLine($entry.wire_json);$entry.response='TTL_WRITE_RETURNED_EXECUTION_NOT_ACKNOWLEDGED';Save-PickupJournal;return
        }
        $geometryPath=$null;$geometryHelper=$pickupHelper
        if($Plan.loaded_route_geometry_plan){$geometryPath=$Plan.loaded_route_geometry_plan;$geometryHelper=Join-Path $PSScriptRoot 'prepare_mode_b_loaded_route.py'}
        elseif($Plan.phase -eq 'DESCEND'){$geometryPath=$pickupJournal.descent_plan}
        elseif($Plan.phase -eq 'LIFT'){$geometryPath=$pickupJournal.lift_plan}
        if($geometryPath -and -not $pickupObserveResidualsOnly){
            $process=[Diagnostics.Process]::new();$process.StartInfo.FileName=$pickupPython
            $process.StartInfo.Arguments='-B -X utf8 "'+$geometryHelper+'" --serve-plan "'+$geometryPath+'"'
            $process.StartInfo.UseShellExecute=$false;$process.StartInfo.CreateNoWindow=$true
            $process.StartInfo.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
            $process.StartInfo.RedirectStandardInput=$true;$process.StartInfo.RedirectStandardOutput=$true
            [void]$process.Start();$ready=$process.StandardOutput.ReadLineAsync()
            if(-not $ready.Wait(5000) -or ($ready.GetAwaiter().GetResult()|ConvertFrom-Json).status -ne 'READY_LOCAL_GEOMETRY_ONLY'){throw 'TTL geometry service unavailable.'}
        }
        foreach($frame in $Plan.stage.stream_frames){
            $sampleTimer=[Diagnostics.Stopwatch]::StartNew();Read-SerialAvailable
            if(($frameIndex%3) -eq 0 -or $timer.Elapsed.TotalMilliseconds-$lastQuery -gt 200){
                $endpoint.WriteLine('{"T":105}');$lastQuery=$timer.Elapsed.TotalMilliseconds
            }
            Read-SerialAvailable
            if(([DateTimeOffset]::UtcNow-$feedbackState.received).TotalSeconds -gt 2){throw 'TTL feedback stale; no following sample.'}
            foreach($name in @('b','s','e','t','r','g')){
                if([Math]::Abs(([double]$feedbackState.latest.$name-[double]$frame.command_firmware_rad.$name)*180/[Math]::PI) -gt [double]$Plan.commissioning_tolerance_profile.moving_tracking_limit_deg -and -not $pickupObserveResidualsOnly){throw ('TTL tracking limit '+$name)}
            }
            if($process){
                $q=@('b','s','e','t','r','g')|ForEach-Object{[double]$feedbackState.latest.$_}
                $line=if($Plan.loaded_route_geometry_plan){[ordered]@{q=@($q);carrying=[bool]$Plan.carrying;phase=$Plan.phase}|ConvertTo-Json -Compress}else{ConvertTo-Json -InputObject @($q) -Compress}
                if($line -ne $geometrySignature){
                    $process.StandardInput.WriteLine($line);$process.StandardInput.Flush();$result=$process.StandardOutput.ReadLineAsync()
                    if(-not $result.Wait(2000)){throw 'TTL geometry deadline.'};$geometry=$result.GetAwaiter().GetResult()|ConvertFrom-Json
                    if($geometry.error){throw ('TTL geometry: '+$geometry.error)}
                    if(-not $Plan.loaded_route_geometry_plan -and [double]$geometry.height_mm -lt 2){throw 'TTL fingertip clearance below bound.'}
                    $geometrySignature=$line
                }
            }
            $entry=[ordered]@{label=$Plan.phase;wire_json=$frame.wire_json;attempted_utc=[DateTimeOffset]::UtcNow.ToString('o');response=$null}
            $pickupJournal.requests+=$entry;$pickupJournal.motion_requests++;$pickupJournal.status=$Plan.phase+'_TTL_SAMPLE_ATTEMPTED_ONCE'
            $entry|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $pickupRun ($Plan.phase+'_TTL_REQUESTS.jsonl')) -Encoding UTF8
            $endpoint.WriteLine($frame.wire_json);$entry.response='TTL_WRITE_RETURNED_EXECUTION_NOT_ACKNOWLEDGED'
            if($timer.Elapsed.TotalMilliseconds-$lastSave -ge 1000){Save-PickupJournal;$lastSave=$timer.Elapsed.TotalMilliseconds}
            $remaining=[int][Math]::Ceiling(1000*[double]$Plan.stage.period_s-$sampleTimer.Elapsed.TotalMilliseconds)
            if($remaining -gt 0){Start-Sleep -Milliseconds $remaining};$frameIndex++
        }
        Save-PickupJournal;Write-Host ($Plan.phase+'_TTL_STREAM_FINISHED')
    } finally {
        if($endpoint){if($endpoint.IsOpen){$endpoint.Close()};$endpoint.Dispose()}
        if($process){if(-not $process.HasExited){$process.StandardInput.Close();if(-not $process.WaitForExit(1000)){$process.Kill()}};$process.Dispose()}
    }
}
