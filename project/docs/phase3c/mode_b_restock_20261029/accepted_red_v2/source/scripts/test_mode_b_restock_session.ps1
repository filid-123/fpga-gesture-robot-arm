param([Parameter(Mandatory=$true)][string]$Session,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
[void][IO.Directory]::CreateDirectory($Output)
$testDll=Join-Path $Output ('RestockEngine_'+[guid]::NewGuid().ToString('N')+'.dll')
Add-Type -Path (Join-Path $root 'pc\mode_b\RestockSerialSession.cs') -ReferencedAssemblies @('System.dll','System.Web.Extensions.dll') -OutputAssembly $testDll
Add-Type -Path $testDll
$testSource=@'
using System;
using System.Collections.Generic;
using System.Web.Script.Serialization;
using ModeB;
public sealed class FakeRestockClock : IRestockClock {
    public double Now; public double Milliseconds {get{return Now;}}
    public void Pause(int ms) {Now+=ms;}
}
public sealed class FakeRestockPort : IRestockPort {
    public bool Closed, Opened; public int FaultAt=-1, SilenceAt=-1, WriteFailAt=-1, CongestionAt=-1;
    public bool Drift, Late, TorqueOff; public int Motion, WriteDelayMs;
    public List<string> Wires=new List<string>(); public List<double> Times=new List<double>();
    public IRestockClock Clock; public double[] Q; public string Pending="";
    readonly JavaScriptSerializer json=new JavaScriptSerializer();
    public FakeRestockPort(IRestockClock c,double[] q){Clock=c;Q=(double[])q.Clone();}
    public void Open(){Opened=true;}
    public void Dispose(){Closed=true;}
    public int BytesToWrite {get{return Motion==CongestionAt ? 1024 : 0;}}
    public string ReadAvailable(){string s=Pending;Pending="";return s;}
    public void WriteLine(string wire){
        var d=json.Deserialize<Dictionary<string,object>>(wire);int t=Convert.ToInt32(d["T"]);
        if(t==105){
            if(SilenceAt>=0 && Motion>=SilenceAt)return;
            var state=new Dictionary<string,object>{{"T",1051},{"x",0},{"y",0},{"z",0},{"tit",0},
                {"b",Q[0]},{"s",Q[1]},{"e",Q[2]},{"t",Q[3]},{"r",Q[4]},{"g",Q[5]},
                {"Stalltor",FaultAt>=0 && Motion>=FaultAt},{"torswitchS",TorqueOff && Motion>=20 ? 0 : 1}};
            if(Drift && Motion>0)state["s"]=Q[1]+.6;
            Pending+=json.Serialize(state)+"\n";return;
        }
        Wires.Add(wire);Times.Add(Clock.Milliseconds);Motion++;
        if(Motion==WriteFailAt)throw new System.IO.IOException("Injected write failure");
        if(t==102){string[] keys={"base","shoulder","elbow","wrist","roll","hand"};
            for(int i=0;i<6;i++)Q[i]=Convert.ToDouble(d[keys[i]]);
            if(WriteDelayMs>0)((FakeRestockClock)Clock).Now+=WriteDelayMs;}
        else Q[5]=Convert.ToDouble(d["cmd"]);
        if(Late && Motion%31==0)((FakeRestockClock)Clock).Now+=57;
    }
}
'@
Add-Type -TypeDefinition $testSource -ReferencedAssemblies @('System.dll','System.Web.Extensions.dll',[ModeB.RestockSerialSession].Assembly.Location)
$raw=[IO.File]::ReadAllText((Resolve-Path -LiteralPath $Session).Path)
$packet=$raw|ConvertFrom-Json
[void][IO.Directory]::CreateDirectory($Output)
$passed=@()
function Assert-Test([bool]$Value,[string]$Name){if(-not $Value){throw ('FAILED: '+$Name)};$script:passed+=@($Name)}
$valid='{"T":1051,"b":0,"s":0,"e":0,"t":0.123,"r":0,"g":0,"x":1,"y":2,"z":3,"tit":0}'
Assert-Test ($null -ne [ModeB.RestockSerialSession]::ParseState($valid)) 'T and wrist t parsed independently'
Assert-Test ($null -eq [ModeB.RestockSerialSession]::ParseState($valid.Replace('"t":0.123','"t":0.1,"t":0.2'))) 'duplicate joint rejected'
Assert-Test ($null -eq [ModeB.RestockSerialSession]::ParseState($valid.Replace('"s":0','"s":"0"'))) 'string joint rejected'
$expected=@($packet.operations|ForEach-Object{$_.wires}|ForEach-Object{[string]$_})
foreach($mode in @('normal','late','residual','fault','silent','write','backpressure','torque','entry','stop','slow_write')){
    $fakeClock=[FakeRestockClock]::new();$fake=[FakeRestockPort]::new($fakeClock,[double[]]$packet.start)
    switch($mode){
        'late' {$fake.Late=$true}
        'residual' {$fake.Drift=$true}
        'fault' {$fake.FaultAt=20}
        'silent' {$fake.SilenceAt=1}
        'write' {$fake.WriteFailAt=20}
        'backpressure' {$fake.CongestionAt=20}
        'torque' {$fake.TorqueOff=$true}
        'entry' {$fake.Q[1]+=1}
        'slow_write' {$fake.WriteDelayMs=14}
    }
    $folder=Join-Path $Output $mode
    if($mode -eq 'stop'){
        [void][IO.Directory]::CreateDirectory($folder)
        [IO.File]::WriteAllText((Join-Path $folder 'STOP_REQUESTED'),'test')
    }
    $runner=[ModeB.RestockSerialSession]::new($fake,$fakeClock,$folder)
    $failed=$false
    try{$runner.Run($raw)}catch{$failed=$true}
    $result=Get-Content -LiteralPath (Join-Path $folder 'RESTOCK_RESULT.json') -Raw|ConvertFrom-Json
    $shouldFail=$mode -in @('fault','silent','write','backpressure','torque','entry','stop')
    Assert-Test ($failed -eq $shouldFail) ($mode+' expected outcome')
    Assert-Test ($fake.Closed -and $result.serial_closed) ($mode+' port disposed')
    for($i=0;$i -lt $fake.Wires.Count;$i++){
        if($fake.Wires[$i] -cne $expected[$i]){throw 'Wire changed/skipped/retried'}
    }
    Assert-Test ($fake.Wires.Count -le $expected.Count) ($mode+' exact ordered prefix no retries')
    if(-not $shouldFail){
        Assert-Test ($fake.Wires.Count -eq $expected.Count -and $result.release_observed -and $result.inventory_restored) ($mode+' complete original sequence')
        $index=0
        foreach($op in $packet.operations){
            if($op.kind -eq 'stream'){
                for($j=1;$j -lt $op.wires.Count;$j++){
                    if($fake.Times[$index+$j]-$fake.Times[$index+$j-1] -lt 20){throw 'Compressed catch-up interval'}
                }
            }
            $index+=$op.wires.Count
        }
        Assert-Test ($true) ($mode+' never compresses20ms intervals')
        if($mode -eq 'slow_write'){
            Assert-Test (@($result.timing|Where-Object{$_.submission_ms -gt $_.nominal_ms+1}).Count -eq 0) 'blocking14ms writes included in20ms period'
        }
    }else{
        Assert-Test (-not $result.inventory_restored -and $fake.Wires.Count -lt $expected.Count) ($mode+' stops remaining sequence')
    }
}
$realtime=$raw|ConvertFrom-Json
$short=$realtime.operations|Where-Object{$_.label -eq 'RESTOCK_BUFFER_OPEN'}
$short.wires=@($short.wires|Select-Object -First 100)
$realtime.operations=@($short);$realtime.requests=100
$realClock=[ModeB.RestockClock]::new();$fake=[FakeRestockPort]::new($realClock,[double[]]$packet.start)
$runner=[ModeB.RestockSerialSession]::new($fake,$realClock,(Join-Path $Output 'realtime'))
$runner.Run(($realtime|ConvertTo-Json -Depth 30 -Compress))
$realResult=Get-Content -LiteralPath (Join-Path $Output 'realtime\RESTOCK_RESULT.json') -Raw|ConvertFrom-Json
Assert-Test ($realResult.timing[0].submission_ms -ge 2000 -and $realResult.timing[0].submission_ms -lt 2500) 'real Windows20ms schedule within25percent overhead'
@{passed=$true;checks=$passed;hardware_accessed=$false;original_requests=$expected.Count;real_clock_stream_ms=$realResult.timing[0].submission_ms}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $Output 'TEST_RESULT.json') -Encoding UTF8
Write-Host ('SESSION_TESTS_PASS: '+$passed.Count)
