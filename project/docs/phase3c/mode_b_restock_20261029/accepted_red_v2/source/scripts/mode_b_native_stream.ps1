# Shared native commissioning stream; dot-source only. No top-level device requests.
function Send-PickupWire {
    param([string]$Wire)
    $uri='http://'+$ArmAddress+'/js?json='+[Uri]::EscapeDataString($Wire)
    return [string](Invoke-WebRequest -UseBasicParsing -DisableKeepAlive -Uri $uri -TimeoutSec 3).Content
}
function Save-PickupJournal {
    $pickupJournal | ConvertTo-Json -Depth 35 | Set-Content -LiteralPath $pickupLog -Encoding UTF8
}
function Read-PickupFeedback {
    param([string]$Label)
    $captureRoot = Join-Path $pickupRun $Label
    & (Join-Path $PSScriptRoot 'collect_mode1_pose.ps1') -PoseId $Label -ArmAddress $ArmAddress `
        -SampleCount 5 -TimeoutSeconds 15 -ReadReconnectAttempts 0 -OutputRoot $captureRoot | Out-Host
    $files = @(Get-ChildItem -LiteralPath $captureRoot -Filter 'POSE_CAPTURE.json' -File -Recurse)
    if ($files.Count -ne 1) { throw 'Expected one current capture.' }
    $capture = Get-Content -LiteralPath $files[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($capture.observation_status -ne 'CAPTURE_COMPLETE_NOT_VALIDATED' -or $capture.samples.Count -ne 5) {
        throw 'Incomplete feedback; no following motion.'
    }
    foreach ($sample in $capture.samples) {
        if ($sample.feedback.Stalltor -or $sample.feedback.Stalltep -or $sample.feedback.Stallvol) { throw 'Firmware fault.' }
    }
    $pickupJournal.observations += $files[0].FullName
    Save-PickupJournal
    return [pscustomobject]@{Path=$files[0].FullName; Capture=$capture}
}
function Wait-PickupArrival {
    param($Target,[string]$Label,$Tolerances)
    if($pickupObserveResidualsOnly){
        Start-Sleep -Milliseconds 250
        $post=Read-PickupFeedback -Label ($Label+'_OBSERVED')
        $last=$post.Capture.samples[-1];$residual=[ordered]@{}
        foreach($name in @('b','s','e','t','r','g')){
            $residual[$name]=([double]$last.joint_rad.$name-[double]$Target.$name)*180/[Math]::PI
        }
        $pickupJournal['final_capture']=$post.Path;$pickupJournal['final_firmware_rad']=$last.joint_rad
        $pickupJournal['residual_observations']+=@([ordered]@{phase=$Label;joint_error_deg=$residual;arrival_accepted=$false})
        Save-PickupJournal
        Write-Host ('FEEDBACK_OBSERVED_WITHOUT_RESIDUAL_STOP: '+$Label)
        return $post
    }
    $timer=[Diagnostics.Stopwatch]::StartNew(); $arrivals=0; $off=0; $index=0
    while ($timer.Elapsed.TotalSeconds -lt 40) {
        $index++
        $post=Read-PickupFeedback -Label ($Label+'_{0:D2}' -f $index)
        $last=$post.Capture.samples[-1]; $stable=$true; $within=$true; $worst=0.0
        foreach ($name in @('b','s','e','t','r','g')) {
            if ([double]$post.Capture.observed_joint_range_deg.$name -gt .5) { $stable=$false }
            $err=[Math]::Abs(([double]$last.joint_rad.$name-[double]$Target.$name)*180/[Math]::PI)
            $worst=[Math]::Max($worst,$err)
            if ($err -gt [double]$Tolerances.$name) { $within=$false }
        }
        if ($stable -and $within) { $arrivals++ } else { $arrivals=0 }
        if ($arrivals -ge 2) {
            $pickupJournal.final_capture=$post.Path; $pickupJournal.final_firmware_rad=$last.joint_rad
            Save-PickupJournal
            Write-Host ('PICKUP_FEEDBACK_WITHIN_PRACTICAL_TOLERANCE: '+$Label)
            return $post
        }
        if ($stable -and -not $within -and $timer.Elapsed.TotalSeconds -ge 8) { $off++ } else { $off=0 }
        if ($off -ge 3) { throw ('Stable outside practical bounds ({0:F2}deg); no resend.' -f $worst) }
    }
    throw 'Arrival not established; no following motion.'
}
function Invoke-PickupStream {
    param($Plan)
    if ($Plan.stage.native_wire_json) {
        $request=[ordered]@{label=$Plan.phase; wire_json=$Plan.stage.native_wire_json;
            attempted_utc=[DateTimeOffset]::UtcNow.ToString('o'); response=$null}
        $pickupJournal.requests+=$request; $pickupJournal.motion_requests++; $pickupJournal.status='NATIVE_HOME_REQUEST_ATTEMPTED_ONCE'
        Save-PickupJournal
        $nativeUri='http://'+$ArmAddress+'/js?json='+[Uri]::EscapeDataString($Plan.stage.native_wire_json)
        $request.response=[string](Invoke-WebRequest -UseBasicParsing -DisableKeepAlive -Headers @{'Cache-Control'='no-cache, no-store'} -Uri $nativeUri -TimeoutSec 5).Content
        Save-PickupJournal
        Write-Host ('NATIVE_REQUESTED_ONCE: '+$Plan.phase)
        return
    }
    . (Join-Path $PSScriptRoot 'roarm_state_json.ps1')
    $socket=[Net.WebSockets.ClientWebSocket]::new()
    $cancel=[Threading.CancellationTokenSource]::new()
    $message=[IO.MemoryStream]::new(); $buffer=New-Object byte[] 8192
    $segment=[ArraySegment[byte]]::new($buffer)
    $state=@{receive=$null; latest=$null; latestTime=[DateTimeOffset]::MinValue; pending=$false;
             seenSnapshots=[Collections.Generic.HashSet[string]]::new(); latestSignature=$null}
    $timer=[Diagnostics.Stopwatch]::StartNew(); $lastQuery=-10000.0; $lastSave=-10000.0
    $feedbackLog=Join-Path $pickupRun ($Plan.phase+'_STREAM_FEEDBACK.jsonl')
    $receiptLog=Join-Path $pickupRun ($Plan.phase+'_STREAM_RECEIPTS.jsonl')
    $requestLog=Join-Path $pickupRun ($Plan.phase+'_STREAM_REQUESTS.jsonl')
    $geometryProcess=$null; $geometrySignature=$null; $geometryHeight=0.0
    function Read-PickupStreamAvailable {
        while ($state.receive -and $state.receive.IsCompleted) {
            $result=$state.receive.GetAwaiter().GetResult()
            if ($result.MessageType -eq 'Close') { throw 'Feedback socket closed; no following sample.' }
            $message.Write($buffer,0,$result.Count)
            if ($result.EndOfMessage) {
                $raw=[Text.Encoding]::UTF8.GetString($message.ToArray()); $message.SetLength(0)
                $feedback=ConvertFrom-RoArmStateJson -RawJson $raw
                if ($null -ne $feedback) {
                    if ($feedback.Stalltor -or $feedback.Stalltep -or $feedback.Stallvol) { throw 'Firmware fault.' }
                    Add-Content -LiteralPath $feedbackLog -Value $raw -Encoding UTF8
                    # This firmware mixes progressing -15 states with repeated
                    # 1051 snapshots of an earlier T105. Do not let an old
                    # snapshot overwrite newer progress on a vertical path.
                    $accept=$true
                    $signature=(@('b','s','e','t','r','g','x','y','z','tit') | ForEach-Object { [string]$feedback.$_ }) -join '|'
                    if ($null -ne $state.latest) {
                        $backtrack=if ($Plan.phase -eq 'DESCEND') {
                            [double]$feedback.z-[double]$state.latest.z
                        } else { [double]$state.latest.z-[double]$feedback.z }
                        if ($Plan.phase -notin @('DESCEND','LIFT')) {
                            $progressNew=0.0; $progressLast=0.0; $progressScale=0.0
                            foreach ($axis in @('b','s','e','t','r','g')) {
                                $delta=[double]$Plan.stage.target_firmware_rad.$axis-[double]$Plan.start_firmware_rad.$axis
                                $progressNew+=([double]$feedback.$axis-[double]$Plan.start_firmware_rad.$axis)*$delta
                                $progressLast+=([double]$state.latest.$axis-[double]$Plan.start_firmware_rad.$axis)*$delta
                                $progressScale+=$delta*$delta
                            }
                            $backtrack=if ($progressScale -gt .000001) { 100*($progressLast-$progressNew)/$progressScale } else { 0 }
                        }
                        if ($feedback.message_type -eq 1051 -and $backtrack -gt 3 -and $state.seenSnapshots.Contains($signature)) {
                            $accept=$false
                        }
                    }
                    ([ordered]@{received_utc=[DateTimeOffset]::UtcNow.ToString('o'); accepted_as_current=$accept;
                        message_type=$feedback.message_type; endpoint_z=$feedback.z} | ConvertTo-Json -Compress) |
                        Add-Content -LiteralPath $receiptLog -Encoding UTF8
                    if ($accept) {
                        $state.latest=$feedback
                        $state.latestTime=[DateTimeOffset]::UtcNow; $state.latestSignature=$signature
                        if ($feedback.message_type -eq 1051) { $state.pending=$false }
                        if ($feedback.message_type -eq 1051) { [void]$state.seenSnapshots.Add($signature) }
                    }
                }
            }
            $state.receive=$socket.ReceiveAsync($segment,$cancel.Token)
        }
    }
    try {
        if ($Plan.phase -in @('DESCEND','LIFT') -or $Plan.loaded_route_geometry_plan) {
            $geometryPlanPath=if ($Plan.phase -eq 'DESCEND') { $pickupJournal.descent_plan } else { $pickupJournal.lift_plan }
            $geometryHelperPath=$pickupHelper
            if ($Plan.loaded_route_geometry_plan) { $geometryPlanPath=$Plan.loaded_route_geometry_plan; $geometryHelperPath=Join-Path $PSScriptRoot 'prepare_mode_b_loaded_route.py' }
            $geometryProcess=[Diagnostics.Process]::new()
            $geometryProcess.StartInfo.FileName=$pickupPython
            $geometryProcess.StartInfo.Arguments='-B -X utf8 "'+$geometryHelperPath+'" --serve-plan "'+$geometryPlanPath+'"'
            $geometryProcess.StartInfo.UseShellExecute=$false; $geometryProcess.StartInfo.CreateNoWindow=$true
            $geometryProcess.StartInfo.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
            $geometryProcess.StartInfo.RedirectStandardInput=$true; $geometryProcess.StartInfo.RedirectStandardOutput=$true
            [void]$geometryProcess.Start()
            $readyTask=$geometryProcess.StandardOutput.ReadLineAsync()
            if (-not $readyTask.Wait(5000)) { throw 'Local geometry service unavailable; no stream.' }
            $ready=$readyTask.GetAwaiter().GetResult() | ConvertFrom-Json
            if ($ready.status -ne 'READY_LOCAL_GEOMETRY_ONLY') { throw 'Local geometry service failed.' }
        }
        $cancel.CancelAfter(5000)
        $socket.ConnectAsync([Uri]('ws://'+$ArmAddress+'/ws'),$cancel.Token).GetAwaiter().GetResult() | Out-Null
        $cancel.CancelAfter(180000)
        $state.receive=$socket.ReceiveAsync($segment,$cancel.Token)
        $queryUri='http://'+$ArmAddress+'/js?json='+[Uri]::EscapeDataString('{"T":105}')
        Invoke-WebRequest -UseBasicParsing -Uri $queryUri -TimeoutSec 3 | Out-Null
        $state.pending=$true
        while ($null -eq $state.latest -and $timer.Elapsed.TotalSeconds -lt 5) {
            Read-PickupStreamAvailable; Start-Sleep -Milliseconds 5
        }
        if ($null -eq $state.latest) { throw 'No current feedback; no trajectory sent.' }
        foreach ($name in @('b','s','e','t','r','g')) {
            $startLimit=if ($Plan.loaded_route_geometry_plan) { [double]$Plan.arrival_tolerance_deg.$name } else { .5 }
            if ([Math]::Abs(([double]$state.latest.$name-[double]$Plan.start_firmware_rad.$name)*180/[Math]::PI) -gt $startLimit) {
                throw 'Pose changed after preparation; no stream sent.'
            }
        }
        $lastQuery=$timer.Elapsed.TotalMilliseconds
        foreach ($frame in $Plan.stage.stream_frames) {
            $frameTimer=[Diagnostics.Stopwatch]::StartNew()
            Read-PickupStreamAvailable
            # Refresh before interpreting a lagging snapshot as actuator error.
            # Only read-only T105 is repeated; motion samples are never resent.
            $refreshNeeded=(([DateTimeOffset]::UtcNow-$state.latestTime).TotalMilliseconds -gt 1000)
            foreach ($name in @('b','s','e','t','r','g')) {
                if ($name -eq 'g' -and $Plan.phase -eq 'LIFT') { continue }
                if ([Math]::Abs(([double]$state.latest.$name-[double]$frame.command_firmware_rad.$name)*180/[Math]::PI) -gt 6) { $refreshNeeded=$true }
            }
            if ($refreshNeeded) {
                $refreshStarted=[DateTimeOffset]::UtcNow
                $freshQueryUri=$queryUri+'&read_nonce='+[DateTime]::UtcNow.Ticks
                Invoke-WebRequest -UseBasicParsing -DisableKeepAlive -Headers @{'Cache-Control'='no-cache, no-store'} -Uri $freshQueryUri -TimeoutSec 3 | Out-Null
                $refreshTimer=[Diagnostics.Stopwatch]::StartNew()
                do {
                    Read-PickupStreamAvailable
                    $freshWithin=$true
                    foreach ($axis in @('b','s','e','t','r','g')) {
                        if ($axis -eq 'g' -and $Plan.phase -eq 'LIFT') { continue }
                        if ([Math]::Abs(([double]$state.latest.$axis-[double]$frame.command_firmware_rad.$axis)*180/[Math]::PI) -gt 6) { $freshWithin=$false }
                    }
                    if ($state.latestTime -ge $refreshStarted -and $freshWithin) { break }
                    Start-Sleep -Milliseconds 5
                } while ($refreshTimer.Elapsed.TotalMilliseconds -lt 1000)
                $lastQuery=$timer.Elapsed.TotalMilliseconds
            }
            if (([DateTimeOffset]::UtcNow-$state.latestTime).TotalMilliseconds -gt 2000) { throw 'Stale feedback; no following sample.' }
            foreach ($name in @('b','s','e','t','r','g')) {
                $trackingLimit=[double]$Plan.commissioning_tolerance_profile.moving_tracking_limit_deg
                if ([Math]::Abs(([double]$state.latest.$name-[double]$frame.command_firmware_rad.$name)*180/[Math]::PI) -gt $trackingLimit) {
                    throw ('Excess tracking deviation: '+$name)
                }
            }
            if ($Plan.loaded_route_geometry_plan) {
                $joints=@('b','s','e','t','r','g') | ForEach-Object { [double]$state.latest.$_ }
                $geometryInput=[ordered]@{q=@($joints);carrying=[bool]$Plan.carrying} | ConvertTo-Json -Compress
                if ($geometryInput -ne $geometrySignature) {
                    $geometryProcess.StandardInput.WriteLine($geometryInput); $geometryProcess.StandardInput.Flush()
                    $geometryTask=$geometryProcess.StandardOutput.ReadLineAsync()
                    if (-not $geometryTask.Wait(2000)) { throw 'Loaded-route geometry timed out; no following sample.' }
                    $geometryResult=$geometryTask.GetAwaiter().GetResult() | ConvertFrom-Json
                    if ($geometryResult.error) { throw ('Loaded-route geometry: '+$geometryResult.error) }
                    $geometrySignature=$geometryInput
                }
            }
            if ($Plan.phase -in @('DESCEND','LIFT')) {
            $pitchDelta=[Math]::Abs(([double]$state.latest.tit-[double]$Plan.firmware_reference_start_endpoint[3])*180/[Math]::PI)
            $joints=@('b','s','e','t','r','g') | ForEach-Object { [double]$state.latest.$_ }
            $jointLine=ConvertTo-Json -InputObject @($joints) -Compress
            if ($jointLine -ne $geometrySignature) {
                $geometryProcess.StandardInput.WriteLine($jointLine); $geometryProcess.StandardInput.Flush()
                $geometryTask=$geometryProcess.StandardOutput.ReadLineAsync()
                if (-not $geometryTask.Wait(1500)) { throw 'Local geometry evaluation timed out; no following sample.' }
                $geometryResult=$geometryTask.GetAwaiter().GetResult() | ConvertFrom-Json
                if ($geometryResult.error -or $null -eq $geometryResult.height_mm) { throw 'Invalid current local geometry.' }
                $geometryHeight=[double]$geometryResult.height_mm; $geometrySignature=$jointLine
            }
            $clearanceFloor=if ($Plan.phase -eq 'LIFT') { [double]$Plan.commissioning_tolerance_profile.lifting_fingertip_model_floor_mm } else { [double]$Plan.commissioning_tolerance_profile.descending_fingertip_model_floor_mm }
            $orientationWithin=if ($Plan.phase -eq 'LIFT') {
                [Math]::Abs(([double]$state.latest.tit-[Math]::PI/2)*180/[Math]::PI) -le [double]$Plan.commissioning_tolerance_profile.loaded_pitch_limit_from_vertical_deg
            } else { $pitchDelta -le 6 }
            if ($geometryHeight -lt $clearanceFloor -or -not $orientationWithin) {
                throw ('Observed local geometry outside bounds: fingertip {0:F2}mm, pitch delta {1:F2}deg.' -f $geometryHeight,$pitchDelta)
            }
            }
            if (-not $state.pending -and $timer.Elapsed.TotalMilliseconds-$lastQuery -ge 800) {
                $periodicQueryUri=$queryUri+'&read_nonce='+[DateTime]::UtcNow.Ticks
                Invoke-WebRequest -UseBasicParsing -DisableKeepAlive -Headers @{'Cache-Control'='no-cache, no-store';'Pragma'='no-cache'} -Uri $periodicQueryUri -TimeoutSec 3 | Out-Null
                $state.pending=$true; $lastQuery=$timer.Elapsed.TotalMilliseconds
            }
            $entry=[ordered]@{label=$Plan.phase; wire_json=$frame.wire_json; attempted_utc=[DateTimeOffset]::UtcNow.ToString('o'); response=$null}
            $pickupJournal.requests += $entry; $pickupJournal.motion_requests++
            $pickupJournal.status=$Plan.phase+'_SAMPLE_ATTEMPTED_ONCE'
            $entry | ConvertTo-Json -Compress | Add-Content -LiteralPath $requestLog -Encoding UTF8
            if ($timer.Elapsed.TotalMilliseconds-$lastSave -ge 1000) { Save-PickupJournal; $lastSave=$timer.Elapsed.TotalMilliseconds }
            $uri='http://'+$ArmAddress+'/js?json='+[Uri]::EscapeDataString($frame.wire_json)
            $response=Invoke-WebRequest -UseBasicParsing -DisableKeepAlive -Uri $uri -TimeoutSec 3
            $entry.response=[string]$response.Content
            ([ordered]@{sample=$pickupJournal.motion_requests; response=[string]$response.Content} | ConvertTo-Json -Compress) |
                Add-Content -LiteralPath $requestLog -Encoding UTF8
            $remaining=[int][Math]::Ceiling(1000*[double]$Plan.stage.period_s-$frameTimer.Elapsed.TotalMilliseconds)
            if ($remaining -gt 0) { Start-Sleep -Milliseconds $remaining }
        }
        $pickupJournal[$Plan.phase+'_stream_elapsed_seconds']=$timer.Elapsed.TotalSeconds
        Save-PickupJournal
        Write-Host ($Plan.phase+'_CONTINUOUS_STREAM_FINISHED')
    } finally {
        $cancel.Cancel(); $socket.Dispose(); $cancel.Dispose(); $message.Dispose()
        if ($null -ne $geometryProcess) {
            if (-not $geometryProcess.HasExited) { $geometryProcess.StandardInput.Close(); if (-not $geometryProcess.WaitForExit(1000)) { $geometryProcess.Kill() } }
            $geometryProcess.Dispose()
        }
    }
}
