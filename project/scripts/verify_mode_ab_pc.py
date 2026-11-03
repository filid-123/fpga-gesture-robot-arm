"""Run the focused AB software/UI regression set without opening devices."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import re
ROOT=Path(__file__).resolve().parents[1]


def main(out):
    out.mkdir(parents=True,exist_ok=False);commands=[];tests=0;ui_checks=0
    for name in ('control','http','shared_red','snapshot','planning','uploads','family','diagnostics','native','workspace','workspace_install','ui'):
        script=('scripts/test_mode_b_full_workspace'+('_install' if name=='workspace_install' else '')+'.py' if name.startswith('workspace') else 'scripts/test_mode_ab_'+name+'.py')
        command=(['C:/Program Files/nodejs/node.exe',str(ROOT/'scripts/test_mode_ab_ui.cjs')] if name=='ui' else
                 [sys.executable,'-X','utf8','-B',str(ROOT/script)])
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        text=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(name+'.txt')).write_text(text,encoding='utf-8')
        commands.append(dict(name=name,exit_code=r.returncode));print(name,r.returncode,flush=True)
        if r.returncode:raise RuntimeError(text)
        if name=='ui':ui_checks=int(json.loads(text.strip().splitlines()[-1])['checks'])
        else:tests+=int(re.search(r'Ran (\d+) tests?',text).group(1))
    paths=list((ROOT/'pc/mode_ab').glob('*.py'))+list((ROOT/'web/mode-ab').glob('*'))
    paths += [ROOT/('scripts/test_mode_ab_'+n+'.py') for n in ('control','http','shared_red','snapshot','planning','uploads','family','diagnostics')]
    paths += [ROOT/'scripts/test_mode_ab_ui.cjs',ROOT/'scripts/test_mode_ab_native.py',ROOT/'scripts/test_mode_b_full_workspace.py',ROOT/'scripts/test_mode_b_full_workspace_install.py',ROOT/'scripts/apply_mode_b_full_workspace.py',Path(__file__)]
    report=dict(passed=True,pc_tests=tests,ui_checks=ui_checks,commands=commands,hardware_access=False,physical_test='NOT_RUN',
        source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (out/'result.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)
