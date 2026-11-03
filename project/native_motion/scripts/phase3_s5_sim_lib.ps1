<# Helpers of run_phase3_s5_sim.ps1 (dot-sourced; also used by the package tests).

   The generic cmd.exe helpers (ConvertTo-CmdToken, Get-ToolCommandLine, Invoke-ToolBat) are the
   S4 v0.1.1 / S3 v0.1.1 ones: Vivado's xvlog/xelab/xsim are .bat files, cmd.exe splits unquoted
   batch arguments at '=' , ';' and blanks, so every tool call builds its own quoted command line
   and hands it to cmd.exe /d /s /c "..." via ProcessStartInfo.Arguments.  No S5 run takes a
   plusarg or a generic.  RTL is compiled in Verilog mode, testbenches with xvlog -sv.
   The integration testbenches use sim/phase3_s5/rtl/s3_top_event_stub.v, a SIMULATION-ONLY
   module named gesture_autonomous_top_v5_7c: the real S3 top is not compiled in these runs
   (S3 has its own XSim regression in its package). #>

function ConvertTo-CmdToken {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)
    if ($Value -eq "") { return '""' }
    if ($Value -match '["%!^&|<>]') { throw "unsupported character for a cmd.exe argument: $Value" }
    if ($Value -match '[\s=,;()]') { return '"' + $Value + '"' }
    return $Value
}

function Get-ToolCommandLine {
    <# Returns the exact /d /s /c "..." argument string given to cmd.exe. #>
    param(
        [Parameter(Mandatory = $true)][string]$Tool,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$LogFile
    )
    foreach ($path in @($Tool, $LogFile)) {
        if ($path -match '["%!^&|<>]') { throw "unsupported character in path: $path" }
    }
    $tokens = @('"' + $Tool + '"')
    foreach ($a in $Arguments) { $tokens += (ConvertTo-CmdToken $a) }
    return '/d /s /c "' + ($tokens -join ' ') + ' > "' + $LogFile + '" 2>&1"'
}

function Invoke-ToolBat {
    <# Runs a .bat (or .exe) with the arguments intact; returns the exit code. #>
    param(
        [Parameter(Mandatory = $true)][string]$Tool,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$LogFile
    )
    $comspec = $env:ComSpec
    if (-not $comspec) { $comspec = Join-Path $env:SystemRoot "System32\cmd.exe" }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $comspec
    $psi.Arguments = Get-ToolCommandLine -Tool $Tool -Arguments $Arguments -LogFile $LogFile
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WorkingDirectory = (Get-Location).ProviderPath
    $process = [System.Diagnostics.Process]::Start($psi)
    $process.WaitForExit()
    return $process.ExitCode
}

function Get-S5SimSources {
    <# Merged-project paths: trajectory core, S1 v0.1.1, S2 v0.2.3, S4 v0.1.1 (all unchanged), S5. #>
    $robot = @(
        "trajectory_smoothstep_q16_16.v", "trajectory_stream_scheduler.v", "trajectory_axi_lite_top.v",
        "arm_uart_tx.v", "arm_uart_rx.v", "arm_half_duplex_dir_ctrl.v", "arm_joint_unit_mapper.v",
        "arm_frame_formatter.v", "arm_json_feedback_parser.v", "arm_so101_status_parser.v",
        "arm_feedback_watchdog.v", "arm_motion_permission_gate.v", "arm_backend_core.v", "arm_backend_axi_top.v",
        "planner_seq_mult.v", "planner_seq_div.v", "planner_p2p_core.v", "planner_axi_top.v",
        "motion_sample_mux.v", "phase3_s2_motion_top.v",
        "s4_axil_window.v", "s4_motion_link.v", "s4_task_regs.v", "s4_task_fsm.v", "phase3_s4_task_top.v"
    ) | ForEach-Object { "rtl/robot/$_" }
    return [pscustomobject]@{
        Rtl = @($robot) + @("rtl/integration/s5_vision_event_adapter.v", "rtl/integration/phase3_s5_vision_motion_top.v")
        Tb = @("sim/phase3_s5/rtl/s3_top_event_stub.v", "sim/phase3_s5/rtl/tb_s5_vision_event_adapter.v",
               "sim/phase3_s5/rtl/tb_s5_int_happy.v", "sim/phase3_s5/rtl/tb_s5_int_window_reject.v",
               "sim/phase3_s5/rtl/tb_s5_int_stale_fatal.v")
        Include = "sim/phase3_s5/rtl"
        Vectors = @("sim/phase3_s5/vectors/s5_adapter_vectors.mem", "sim/phase3_s5/vectors/s5_integration_config.mem")
    }
}

function Get-S5SimRuns {
    return @(
        [pscustomobject]@{ Name = "s5_vision_event_adapter"; Top = "tb_s5_vision_event_adapter"
                           Expect = "PASS: tb_s5_vision_event_adapter" },
        [pscustomobject]@{ Name = "s5_int_happy"; Top = "tb_s5_int_happy"; Expect = "PASS: tb_s5_int scenario 0:" },
        [pscustomobject]@{ Name = "s5_int_window_reject"; Top = "tb_s5_int_window_reject"; Expect = "PASS: tb_s5_int scenario 1:" },
        [pscustomobject]@{ Name = "s5_int_stale_fatal"; Top = "tb_s5_int_stale_fatal"; Expect = "PASS: tb_s5_int scenario 2:" }
    )
}

function Test-S5SimOutput {
    <# PASS only with exit code 0, a 'PASS:' line, the run's expected text and no FAIL:/Fatal: line. #>
    param([Parameter(Mandatory = $true)]$Run, [AllowEmptyString()][string]$Text, [int]$ExitCode)
    if ($ExitCode -ne 0) { return "FAIL (xsim exit $ExitCode)" }
    if ($Text -match '(?m)^\s*(FAIL:|Fatal:|FATAL)') { return "FAIL (self-check)" }
    if ($Text -notmatch '(?m)^PASS:') { return "FAIL (no PASS line)" }
    if (-not $Text.Contains($Run.Expect)) { return "FAIL (PASS line does not contain '$($Run.Expect)')" }
    return "PASS"
}
