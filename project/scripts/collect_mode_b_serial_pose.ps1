param(
    [string]$Port='COM5',
    [ValidateRange(9600,1000000)][int]$Baud=115200,
    [ValidateRange(5,100)][int]$SampleCount=5,
    [ValidateRange(5,60)][int]$TimeoutSeconds=10,
    [string]$PoseId='TTL_CURRENT',
    [string]$OutputRoot
)
# Read-only TTL transport. The only transmitted message is T105 + LF.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'roarm_state_json.ps1')
if (-not $OutputRoot) { $OutputRoot=Join-Path $PSScriptRoot '..\artifacts\phase3c\mode_b_ttl_20261028\captures' }
$out=Join-Path $OutputRoot ($PoseId+'_'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_fffffff'))
[void][IO.Directory]::CreateDirectory($out)
$out=(Resolve-Path -LiteralPath $out).Path
$receipt=Join-Path $out 'POSE_CAPTURE.json'
$capture=[ordered]@{schema='gesture.mode_b.serial_pose_capture.v1';captured_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
    pose_id=$PoseId;transport='TTL_SERIAL';port=$Port;baudrate=$Baud;data_bits=8;parity='N';stop_bits=1
    dtr=$false;rts=$false;observation_status='INCOMPLETE';samples=@();queries=0;motion_commands_sent=0
    error=$null;observed_joint_range_deg=$null}
$serial=[IO.Ports.SerialPort]::new($Port,$Baud,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake=[IO.Ports.Handshake]::None;$serial.DtrEnable=$false;$serial.RtsEnable=$false
$serial.ReadTimeout=100;$serial.WriteTimeout=1000;$serial.NewLine="`n"
$timer=[Diagnostics.Stopwatch]::StartNew();$nextQuery=0.0;$lastSample=-10000.0;$pending=''
try {
    $serial.Open()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds -and $capture.samples.Count -lt $SampleCount) {
        if ($timer.Elapsed.TotalMilliseconds -ge $nextQuery -and $capture.queries -lt 3*$SampleCount) {
            $serial.WriteLine('{"T":105}');$capture.queries++;$nextQuery=$timer.Elapsed.TotalMilliseconds+500
        }
        $part=$serial.ReadExisting()
        if ($part) { $pending+=$part;[IO.File]::AppendAllText((Join-Path $out 'SERIAL_RX.txt'),$part,[Text.Encoding]::UTF8) }
        if ($pending.Length -gt 1048576) { throw 'Serial frame exceeded1MiB.' }
        while ($pending.Contains("`n")) {
            $index=$pending.IndexOf("`n");$line=$pending.Substring(0,$index).Trim();$pending=$pending.Substring($index+1)
            $state=ConvertFrom-RoArmStateJson -RawJson $line
            if ($null -eq $state -or $state.message_type -notin @(-15,1051)) { continue }
            if ($timer.Elapsed.TotalMilliseconds-$lastSample -lt 200) { continue }
            $joints=[ordered]@{};foreach($name in @('b','s','e','t','r','g')){$joints[$name]=[double]$state.$name}
            $capture.samples+=@([ordered]@{received_utc=[DateTimeOffset]::UtcNow.ToString('o');joint_rad=$joints;feedback=$state;raw_json=$line})
            $lastSample=$timer.Elapsed.TotalMilliseconds
            Write-Host ('Captured '+$capture.samples.Count+'/'+$SampleCount)
            if ($capture.samples.Count -ge $SampleCount) { break }
        }
        Start-Sleep -Milliseconds 20
    }
    if ($capture.samples.Count -ne $SampleCount) { throw 'TTL read deadline reached without the requested valid states.' }
    $range=[ordered]@{}
    foreach($name in @('b','s','e','t','r','g')) {
        $values=@($capture.samples|ForEach-Object{[double]$_.joint_rad.$name});$min=($values|Measure-Object -Minimum).Minimum;$max=($values|Measure-Object -Maximum).Maximum
        $range[$name]=($max-$min)*180/[Math]::PI
    }
    $capture.observed_joint_range_deg=$range;$capture.observation_status='CAPTURE_COMPLETE_NOT_VALIDATED'
    Write-Output $capture.samples[-1].raw_json
} catch { $capture.error=$_.Exception.Message;throw } finally {
    if($serial.IsOpen){$serial.Close()};$serial.Dispose()
    $capture|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $receipt -Encoding UTF8
    Write-Host ('SAVED: '+$receipt)
    Write-Host ('STATES: '+$capture.samples.Count+'/'+$SampleCount+'; T105 queries: '+$capture.queries+'; motion commands:0')
}
