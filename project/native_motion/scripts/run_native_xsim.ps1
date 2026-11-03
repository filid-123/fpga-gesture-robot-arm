param([string]$VivadoRoot='E:\Xilinx\2026.1\Vivado',[string[]]$Only=@())
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'phase3_s5_sim_lib.ps1')
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$logs=Join-Path $root 'reports/native_xsim';New-Item -ItemType Directory -Path $logs -Force | Out-Null
$tb=Join-Path $root 'sim/phase3_robot/rtl'
$rtl=@(Get-ChildItem (Join-Path $root 'rtl/robot') -Filter '*.v' | ForEach-Object FullName)
$wrappers=@(Get-ChildItem $tb -Filter '*.v' | Where-Object Name -NotMatch 'window' | ForEach-Object FullName)
Push-Location $root
try {
 $rc=Invoke-ToolBat -Tool "$VivadoRoot/bin/xvlog.bat" -Arguments $rtl -LogFile "$logs/rtl.log"
 if($rc -ne 0){throw "RTL compile: $rc"}
 $rc=Invoke-ToolBat -Tool "$VivadoRoot/bin/xvlog.bat" -Arguments (@('-sv','-i',$tb)+$wrappers) -LogFile "$logs/tb.log"
 if($rc -ne 0){Get-Content "$logs/tb.log" -Tail 12;throw "TB compile: $rc"}
 foreach($f in $wrappers){
  $name=[IO.Path]::GetFileNameWithoutExtension($f)
  if($Only.Count -gt 0 -and $Only -notcontains $name){continue}
  $rc=Invoke-ToolBat -Tool "$VivadoRoot/bin/xelab.bat" -Arguments @($name,'-s',"native_$name") -LogFile "$logs/$name.elab.log"
  if($rc -ne 0){Get-Content "$logs/$name.elab.log" -Tail 12;throw "$name elaboration: $rc"}
  $rc=Invoke-ToolBat -Tool "$VivadoRoot/bin/xsim.bat" -Arguments @("native_$name",'-runall') -LogFile "$logs/$name.run.log"
  $txt=Get-Content "$logs/$name.run.log" -Raw
  if($rc -ne 0 -or $txt -match '(?m)^\s*(FAIL:|Fatal:|FATAL)' -or $txt -notmatch '(?m)^PASS:'){
   Get-Content "$logs/$name.run.log" -Tail 15;throw "$name self-check failed ($rc)"
  }
  ($txt -split "`n" | Where-Object {$_ -match '^PASS:'}) | Write-Output
 }
} finally {Pop-Location}
