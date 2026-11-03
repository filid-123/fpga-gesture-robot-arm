param([string]$Python='',[switch]$VerifyModels)
$ErrorActionPreference='Stop'
if (-not $Python) {
    $Python=(& py -3.12 -c 'import sys; print(sys.executable)').Trim()
}
if (-not (Test-Path -LiteralPath $Python)) {throw 'Install Python 3.12 x64 or pass -Python with its full path.'}
$taskEnv=Join-Path $PSScriptRoot '.venv-ab-rocm'
$taskExe=Join-Path $taskEnv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskExe)) {& $Python -m venv $taskEnv;if ($LASTEXITCODE) {throw 'venv creation failed'}}
& $taskExe -m pip install 'pip==26.2.2'
if ($LASTEXITCODE) {throw 'pip setup failed'}
# Official AMD gfx1151 wheel index. Pin framework and device packages to avoid
# replacing the HIP build with a CPU PyPI torch while installing onnx2torch.
$taskIndex='https://stable.repo.amd.com/rocm/whl-next/'
& $taskExe -m pip install -c (Join-Path $PSScriptRoot 'requirements_mode_ab_lock.txt') --index-url $taskIndex 'torch[device-gfx1151]==2.13.0+rocm10.0.0' 'torchvision[device-gfx1151]==0.28.0+rocm10.0.0'
if ($LASTEXITCODE) {throw 'Official AMD ROCm wheels unavailable; no CPU fallback was installed'}
& $taskExe -m pip install -c (Join-Path $PSScriptRoot 'requirements_mode_ab_lock.txt') -c (Join-Path $PSScriptRoot 'requirements-mode-ab-rocm-constraints.txt') -r (Join-Path $PSScriptRoot 'requirements_mode_ab.txt')
if ($LASTEXITCODE) {throw 'Application dependencies failed'}
& $taskExe -c 'import sys; sys.path.insert(0,sys.argv[1]); from pc.mode_ab.gpu import hip_info; print(hip_info())' $PSScriptRoot
if ($LASTEXITCODE) {throw 'Actual HIP device check failed'}
if ($VerifyModels) {
    $taskOut=Join-Path $PSScriptRoot ('runs/gpu_check_'+(Get-Date -Format 'yyyyMMdd_HHmmss'))
    & $taskExe -X utf8 -B (Join-Path $PSScriptRoot 'scripts/check_mode_ab_gpu.py') --out $taskOut
    if ($LASTEXITCODE) {throw 'Frozen model numerical/localization validation failed'}
}
Write-Output 'ROCm environment ready. Run start_mode_ab.ps1 -CheckOnly before a physical session.'
