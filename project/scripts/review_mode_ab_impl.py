"""Seal the reviewed complete AB implementation, including same-build XSA members."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main(attempt,inspection_name='a1'):
    folder=ROOT/('board_evidence/mode_ab_impl_'+attempt);reports=folder/'implemented_reports';inspection=folder/('inspection_'+inspection_name)
    binding=json.loads((folder/'built_source_hashes.json').read_bytes())
    if not (folder/'build_completed.json').is_file():raise ValueError('Full build incomplete')
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Built source changed: '+name)
    if binding['parameters'].get('DYNAMIC_B')!=1:raise ValueError('Dynamic B is missing')
    if json.loads((inspection/'command.json').read_bytes())['exit_code']!=0:raise ValueError('Netlist inspection incomplete')
    gate=(reports/'build_gate.txt').read_text()
    def row(key):
        v=re.search('^'+key+'=(.*)$',gate,re.M).group(1).split();return {v[i]:float(v[i+1]) for i in range(0,len(v),2)}
    util,timing=row('UTIL'),row('TIMING')
    if re.search('^PROBLEMS=.+$',gate,re.M) or min(timing['WNS'],timing['WHS'])<0 or timing['TNS'] or timing['THS']:raise ValueError('Timing gate failed')
    capacity=dict(LUT_TOTAL=53200,FF=106400,BRAM_TILE=140,DSP=220)
    if any(util[k]>v*.85 for k,v in capacity.items()):raise ValueError('85% resource cap exceeded')
    tr=(reports/'timing_implemented.rpt').read_text()
    for key in ('no_clock','unconstrained_internal_endpoints','multiple_clock','loops'):
        if not re.search('checking '+key+r' \(0\)',tr):raise ValueError('Timing coverage failed: '+key)
    cdc=(reports/'cdc_implemented.rpt').read_text()
    rows=[list(map(int,m)) for m in re.findall(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',cdc,re.M)]
    if len(rows)<3 or any(total!=safe or unsafe or unknown or no_async for total,safe,unsafe,unknown,no_async in rows):raise ValueError('CDC unsafe/unknown endpoint')
    if set(re.findall('CDC-\\d+',(inspection/'CDC_DETAILS.rpt').read_text()))!={'CDC-3','CDC-6'}:raise ValueError('Unexpected CDC classification')
    text=(inspection/'NETLIST_INSPECTION.txt').read_text()
    for key in ('RESULT=PHASE2_POSITIVE_IOB_INPUT_TIMING_AND_NO_REDUNDANT_FRONTEND_PASS',
                'SHARED_CAMERA_RAM_COUNT=8 TYPE=RAMB36E1 PAYLOAD_BYTES=32768','RESTOCK_STATE=1',
                'HDMI_COORDINATE_ROM_RAMB36=1 RAMB18=1 LATENCY_CYCLES=1'):
        if key not in text:raise ValueError('Netlist evidence missing: '+key)
    skew=(inspection/'NETLIST_INSPECTION.txt.bus_skew.rpt').read_text()
    slacks=[float(x) for x in re.findall(r'Slack \(MET\)\s*:\s*([\d.]+)ns',skew)]
    if len(slacks)!=2 or min(slacks)<0 or 'VIOLATED' in skew:raise ValueError('Gray bus skew check failed')
    drc=(reports/'drc_implemented.rpt').read_text()
    if re.search(r'\|\s*(?:Error|Critical Warning)\s*\|',drc):raise ValueError('DRC gate failed')
    warning_classes={name:int(count) for name,count in re.findall(r'^\|\s*([\w-]+)\s*\|\s*Warning\s*\|[^\n]*?\|\s*(\d+)\s*\|',drc,re.M)}
    reset_review=None
    if 'REQP-1839' in warning_classes:
        details=re.findall(r'REQP-1839#\d+ Warning\s+RAMB36 async control check\s+(.*?)(?=\nRelated violations:)',drc,re.S)
        if len(details)!=12 or any('g_b_program.u_player/channel_ram[' not in d or '/WEA[' not in d or 'u_actuator/u_mux/buf_valid_reg' not in d for d in details):
            raise ValueError('Unexpected asynchronous RAM control warning scope')
        proof_path=ROOT/'board_evidence/mode_ab_p4/reset_warning_release/result.json'
        proof=json.loads(proof_path.read_bytes())
        if not proof.get('passed') or not any('asynchronous reset' in c for c in proof['checks']):raise ValueError('Reset invalidation audit missing')
        for name,digest in proof['source_hashes'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Reset audit source changed: '+name)
        reset_review=dict(rule='REQP-1839',count=12,proof=proof_path.relative_to(ROOT).as_posix(),proof_sha256=sha(proof_path),
            reason='Only native volatile-RAM WEA pins see the asynchronously cleared pending flag. COMMIT blocks RAM writes for a live image; reset invalidates committed/base/descriptor masks and backend enable. Interrupted configuration is discarded and fully reloaded/read back; the real-root reset test rejects motion before reload.')
    if set(warning_classes)-{'BUFC-1','DPIP-1','DPOP-1','DPOP-2','PLBUFGOPT-1','REQP-1580','REQP-1839'}:raise ValueError('Unreviewed DRC warning class')
    hwh=(reports/'roarm_closed_loop.hwh').read_text(encoding='utf-8-sig')
    if binding['parameters'].get('FAST_B'):
        ranges=[n.attrib for n in ET.fromstring(hwh).iter('MEMRANGE') if n.attrib.get('SLAVEBUSINTERFACE')=='s_axi_route']
        if len(ranges)!=1 or ranges[0].get('BASEVALUE')!='0x43C20000' or ranges[0].get('HIGHVALUE')!='0x43C20FFF':
            raise ValueError('B native configuration aperture missing from actual PS address map')
    for name in ('TIMED_WALKTHROUGH','HANDOVER_V2','HAND_ALIGN','ENABLE_HDMI','UPGRADE','AUTO_RESTOCK','DYNAMIC_B',*(['FAST_B'] if binding['parameters'].get('FAST_B') else [])):
        if '<PARAMETER NAME="'+name+'" VALUE="1"/>' not in hwh:raise ValueError('HWH feature: '+name)
    artifacts={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [reports/('roarm_closed_loop.'+ext) for ext in ('bit','hwh','xsa')]}
    with zipfile.ZipFile(reports/'roarm_closed_loop.xsa') as z:
        if z.testzip():raise ValueError('XSA CRC')
        for ext in ('bit','hwh'):
            n='roarm_closed_loop.'+ext
            if hashlib.sha256(z.read(n)).hexdigest()!=artifacts[n]['sha256']:raise ValueError('XSA differs from deployed '+ext)
    interactions=(reports/'clock_interaction_implemented.rpt').read_text()
    pairs=[r for r in interactions.splitlines() if 'clk_fpga_1' in r and 'hdmi_clock_wiz' in r]
    if len(pairs)!=2 or not all('Asynchronous Groups' in r for r in pairs):raise ValueError('Clock groups failed')
    if binding['parameters'].get('FAST_B') and 'B_NATIVE_Q16_ROUTE_RAMB36=6' not in text:raise ValueError('Native route memory proof missing')
    result=dict(result='IMPLEMENTATION_NETLIST_TIMING_CDC_SKEW_XSA_PASS',version='0.1.0',task_abi=int(binding['task_abi'],16),
        utilization=util,resource_percent={k:100*util[k]/v for k,v in capacity.items()},timing_ns=timing,
        cdc_endpoints=sum(r[0] for r in rows),cdc_safe=sum(r[1] for r in rows),cdc_unsafe=0,cdc_unknown=0,
        gray_bus_skew_slacks_ns=slacks,drc_errors=0,drc_warning_count=int(re.search(r'Checks found:\s*(\d+)',drc).group(1)),
        artifacts=artifacts,built_input_files=len(binding['files']),source_binding_sha256=sha(folder/'built_source_hashes.json'),
        drc_warning_classes=warning_classes,
        reset_warning_review=reset_review,
        warning_review='SCCB input buffer and clock/serializer phase advisories retained; native blend DSP pipeline recommendations and the narrowly scoped volatile-RAM reset warning are explicitly reviewed. Routed setup/hold/CDC/skew gates must all pass.',
        hardware_test='NOT_RUN',netlist_inspection=inspection_name)
    (folder/'implementation_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);ap.add_argument('--inspection',default='a1');a=ap.parse_args();main(a.attempt,a.inspection)
