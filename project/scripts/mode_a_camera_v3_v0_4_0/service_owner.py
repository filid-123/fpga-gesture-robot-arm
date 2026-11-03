"""Own one hidden hw_server and one bounded diagnostic attempt, then close both."""
from pathlib import Path
import argparse,datetime,hashlib,json,re,subprocess,sys,time

HERE=Path(__file__).resolve().parent


def ps(script):
    return subprocess.check_output(['powershell.exe','-NoProfile','-Command',script],
        creationflags=subprocess.CREATE_NO_WINDOW).decode('utf-8-sig').strip()


def listeners():
    output=ps('''$rows=@(Get-NetTCPConnection -State Listen -LocalPort 3121 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {Get-CimInstance Win32_Process -Filter "ProcessId = $_" | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath}); ConvertTo-Json -Compress -InputObject $rows''')
    return json.loads(output) if output else []


def ancestry(pid):
    output=ps(f'''$taskPid={int(pid)};$rows=@();for($i=0;$i -lt 8 -and $taskPid -gt 0;$i++){{$p=Get-CimInstance Win32_Process -Filter "ProcessId = $taskPid";if(-not $p){{break}};$rows+=($p | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath);$taskPid=$p.ParentProcessId}};ConvertTo-Json -Compress -InputObject $rows''')
    return json.loads(output) if output else []


def command(tokens):
    values=list(map(str,tokens))
    assert not any(re.search(r'["%!^&|<>]',v) for v in values)
    return 'cmd.exe /d /s /c "'+' '.join('"'+v+'"' for v in values)+'"'
