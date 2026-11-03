param(
    [Parameter(Mandatory = $true)][string]$NpuPython,
    [Parameter(Mandatory = $true)][string]$RocmPython,
    [Parameter(Mandatory = $true)][string]$ProviderOptions,
    [ValidateSet('BF16', 'XINT8')][string]$Precision = 'BF16',
    [string]$NpuPackage,
    [ValidateRange(1, 10000)][int]$Runs = 30,
    [string]$Output
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskRoot
function Invoke-LoggedPython([string]$Executable, [string[]]$Arguments, [string]$Log) {
    # Native SDK stderr is evidence, not necessarily a failure. Decide by exit code.
    $taskOldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Executable @Arguments 1> $Log 2> ($Log + '.stderr.txt'); $taskExit = $LASTEXITCODE }
    finally { $ErrorActionPreference = $taskOldPreference }
    if ($taskExit -ne 0) { throw "Python step failed (exit $taskExit). See $Log and its stderr file." }
}
$taskOut = $null
$taskStep = 'validate_arguments'
try {
    foreach ($taskFile in @($NpuPython, $RocmPython, $ProviderOptions)) {
        if (-not (Test-Path -LiteralPath $taskFile -PathType Leaf)) { throw "Missing file: $taskFile" }
    }
    $NpuPython = (Resolve-Path -LiteralPath $NpuPython).Path
    $RocmPython = (Resolve-Path -LiteralPath $RocmPython).Path
    $ProviderOptions = (Resolve-Path -LiteralPath $ProviderOptions).Path
    if (-not $Output) { $Output = 'target_results/mode_b_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') }
    $taskFullOut = [System.IO.Path]::GetFullPath((Join-Path $taskRoot $Output))
    $taskRootPrefix = (Resolve-Path -LiteralPath $taskRoot).Path.TrimEnd('\') + '\'
    if (-not $taskFullOut.StartsWith($taskRootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Output must be a new directory inside the extracted package.'
    }
    if (Test-Path -LiteralPath $taskFullOut) { throw 'Choose a new output directory.' }
    New-Item -ItemType Directory -Path $taskFullOut | Out-Null
    $taskOut = $taskFullOut
    Copy-Item -LiteralPath $ProviderOptions -Destination "$taskOut/provider_options.json"
    $taskStep = 'package_hashes'
    Invoke-LoggedPython $NpuPython @('-B', '-X', 'utf8', 'scripts/verify_deployment_archive.py', '.') "$taskOut/package_hashes.txt"
    $taskStep = 'environment'
    Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber |
        ConvertTo-Json | Out-File "$taskOut/os.json" -Encoding utf8
    Get-CimInstance Win32_Processor | Select-Object Name, Manufacturer |
        ConvertTo-Json | Out-File "$taskOut/cpu.json" -Encoding utf8
    Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'NPU|Radeon|IPU' } |
        Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer |
        ConvertTo-Json | Out-File "$taskOut/drivers.json" -Encoding utf8
    Invoke-LoggedPython $NpuPython @('-B', '-X', 'utf8', '-m', 'pip', 'freeze') "$taskOut/npu_packages.txt"
    Invoke-LoggedPython $RocmPython @('-B', '-X', 'utf8', '-m', 'pip', 'freeze') "$taskOut/rocm_packages.txt"
    $taskStep = 'quantize'
    if (-not $NpuPackage) {
        Invoke-LoggedPython $NpuPython @('-B', '-X', 'utf8', 'scripts/quantize_mode_b_deployment.py',
            '--precision', $Precision, '--out', "$taskOut/quantized") "$taskOut/quantize.txt"
        $NpuPackage = "$taskOut/quantized/model.json"
    }
    $taskStep = 'npu_detect'
    Invoke-LoggedPython $NpuPython @('-B', '-X', 'utf8', 'scripts/check_mode_b_deployment.py',
        'detect', '--backend', 'npu', '--package', $NpuPackage, '--runs', "$Runs",
        '--provider-options', "$taskOut/provider_options.json", '--out', "$taskOut/npu_detector") "$taskOut/npu_detector.txt"
    $taskStep = 'rocm_surface'
    Invoke-LoggedPython $RocmPython @('-B', '-X', 'utf8', 'scripts/check_mode_b_deployment.py',
        'surface', '--backend', 'rocm', '--detections', "$taskOut/npu_detector/detector.json",
        '--out', "$taskOut/rocm_surface") "$taskOut/rocm_surface.txt"
    $taskStep = 'same_image_comparison'
    Invoke-LoggedPython $RocmPython @('-B', '-X', 'utf8', 'scripts/check_mode_b_deployment.py',
        'compare', '--candidate', "$taskOut/rocm_surface/surface.json",
        '--out', "$taskOut/comparison.json") "$taskOut/comparison.txt"
    @{status = 'PREVALIDATION_STAGES_COMPLETED_REVIEW_REQUIRED'; physical_execution = $false;
      path_submissions = 0; npu_acceptance = 'REQUIRES_CORE_PLACEMENT_REVIEW';
      rocm_acceptance = 'REQUIRES_DEVICE_VERSION_AND_QUALITY_REVIEW';
      metric_localization_accepted = $false} |
        ConvertTo-Json | Out-File "$taskOut/result.json" -Encoding utf8
    Write-Host "Finished. Return the entire directory plus the completed return template: $taskOut"
}
catch {
    if ($taskOut) {
        @{status = 'ERROR'; failed_step = $taskStep; error = $_.Exception.Message;
          physical_execution = $false; path_submissions = 0; hardware_acceptance = $false} |
            ConvertTo-Json | Out-File "$taskOut/result.json" -Encoding utf8
    }
    throw
}
finally { Pop-Location }
