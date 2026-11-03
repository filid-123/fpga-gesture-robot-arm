"""Review the actual v014 routed design and seal its source/artifact binding."""
from pathlib import Path
import hashlib,json,re,zipfile

ROOT=Path(__file__).resolve().parents[1]
H=ROOT/'board_evidence/mode_a_restock_impl_a2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    binding=json.loads((H/'BUILT_SOURCE_HASHES.json').read_text('utf-8'))
    assert binding['parameters']==dict(TIMED_WALKTHROUGH=1,HANDOVER_V2=1,HAND_ALIGN=1,HAND_ALIGN_REGIONS=4,HAND_ALIGN_LOCATOR=1,ENABLE_HDMI=1,UPGRADE=1,AUTO_RESTOCK=1)
    for name,digest in binding['files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Built input changed '+name)
    assert json.loads((H/'BUILD_COMPLETED.json').read_text('utf-8'))['passed']
    assert json.loads((H/'inspection_a1/COMMAND.json').read_text('utf-8'))['exit_code']==0
    gate=(H/'implemented_reports/build_gate.txt').read_text('utf-8')
    def values(key):
        row=re.search(r'^'+key+r'=(.*)$',gate,re.M).group(1).split()
        return {row[i]:float(row[i+1]) for i in range(0,len(row),2)}
    util,timing=values('UTIL'),values('TIMING')
    assert not re.search(r'^PROBLEMS=(.+)$',gate,re.M)
    assert timing['WNS']>=0 and timing['WHS']>=0 and timing['TNS']==timing['THS']==0
    assert util['LUT_TOTAL']<=45220 and util['FF']<=90440 and util['BRAM_TILE']<=119 and util['DSP']<=187
    timing_report=(H/'implemented_reports/timing_implemented.rpt').read_text('utf-8')
    for name in ('no_clock','unconstrained_internal_endpoints','multiple_clock','loops'):
        assert re.search(r'checking '+name+r' \(0\)',timing_report),name
    cdc=(H/'implemented_reports/cdc_implemented.rpt').read_text('utf-8')
    rows=[list(map(int,m)) for m in re.findall(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',cdc,re.M)]
    assert len(rows)>=3 and sum(r[0] for r in rows)>28
    assert all(r[0]==r[1] and r[2:]==[0,0,0] for r in rows)
    details=(H/'inspection_a1/CDC_DETAILS.rpt').read_text('utf-8')
    # CDC-6 includes Gray pointers plus the explicitly acknowledged stable display buses.
    assert set(re.findall(r'CDC-\d+',details))=={'CDC-3','CDC-6'}
    inspect=(H/'inspection_a1/NETLIST_INSPECTION.txt').read_text('utf-8')
    assert 'RESULT=PHASE2_POSITIVE_IOB_INPUT_TIMING_AND_NO_REDUNDANT_FRONTEND_PASS' in inspect
    assert inspect.count('POSITIVE_IOB=')==10
    assert 'SHARED_CAMERA_RAM_COUNT=8 TYPE=RAMB36E1 PAYLOAD_BYTES=32768' in inspect
    assert 'HDMI_COORDINATE_ROM_RAMB36=1 RAMB18=1 LATENCY_CYCLES=1' in inspect
    assert 'CAMERA_AND_HDMI_MMCM_COUNT=2' in inspect and 'EXCLUDED_REFERENCE=IDELAYE2 COUNT=0' in inspect
    assert inspect.count('BITS=11 SYNC_STAGES=2 BOUND_NS=10.000')==2
    skew=(H/'inspection_a1/NETLIST_INSPECTION.txt.bus_skew.rpt').read_text('utf-8')
    skew_slacks=[float(x) for x in re.findall(r'Slack \(MET\)\s*:\s*([\d.]+)ns',skew)]
    assert len(skew_slacks)==2 and min(skew_slacks)>=0 and 'VIOLATED' not in skew
    drc=(H/'implemented_reports/drc_implemented.rpt').read_text('utf-8')
    assert not re.search(r'\|\s*(?:Error|Critical Warning)\s*\|',drc)
    artifacts={}
    for ext in ('bit','hwh','xsa'):
        p=H/'implemented_reports'/('roarm_closed_loop.'+ext)
        artifacts[p.name]=dict(bytes=p.stat().st_size,sha256=sha(p))
    hwh=(H/'implemented_reports/roarm_closed_loop.hwh').read_text('utf-8')
    for feature in ('TIMED_WALKTHROUGH','HANDOVER_V2','HAND_ALIGN','ENABLE_HDMI','UPGRADE','AUTO_RESTOCK'):
        assert '<PARAMETER NAME="'+feature+'" VALUE="1"/>' in hwh
    assert '<PARAMETER NAME="HAND_ALIGN_REGIONS" VALUE="4"/>' in hwh
    assert '<PARAMETER NAME="HAND_ALIGN_LOCATOR" VALUE="1"/>' in hwh
    with zipfile.ZipFile(H/'implemented_reports/roarm_closed_loop.xsa') as z:
        assert z.testzip() is None
        for ext in ('bit','hwh'):
            name='roarm_closed_loop.'+ext
            assert hashlib.sha256(z.read(name)).hexdigest()==artifacts[name]['sha256']
    audit=json.loads((ROOT/'native_motion/reports/roarm_model_audit.json').read_text('utf-8'))
    assert audit['status']=='PASS' and audit['samples']==26 and audit['layer_checks']==832
    result=dict(result='IMPLEMENTATION_NETLIST_IOB_CDC_SKEW_AND_XSA_PASS',version='0.14.0',task_abi=0x340b,
        utilization=util,resource_max_percent=85,resource_percent={k:round(100*util[k]/v,3) for k,v in {'LUT_TOTAL':53200,'FF':106400,'BRAM_TILE':140,'DSP':220}.items()},timing_ns=timing,unconstrained_internal_endpoints=0,cdc_endpoints=sum(r[0] for r in rows),cdc_safe=sum(r[1] for r in rows),cdc_unsafe=0,cdc_unknown=0,
        gray_bus_skew_slacks_ns=skew_slacks,drc_errors=0,drc_warning_count=int(re.search(r'Checks found:\s*(\d+)',drc).group(1)),drc_warning_rule_types=len(re.findall(r'\|\s*Warning\s*\|',drc)),
        review='Original Gray pointer CDC-6 buses retain10ns skew constraints. HDMI multi-bit CDC-6 buses have two-stage ASYNC_REG, held payload and request/ack, latched only at frame boundaries; focused randomized snapshot/paired-bank tests pass. Other endpoints CDC-3.',
        artifacts=artifacts,hardware_source_binding_sha256=sha(H/'BUILT_SOURCE_HASHES.json'),
        built_input_files=len(binding['files']),model_audit=audit,physical_hardware_test='NOT_RUN')
    # Preserve the inherited XDC parser diagnostic instead of presenting a
    # zero-warning tool run. Clock grouping is independently checked here.
    interactions=(H/'implemented_reports/clock_interaction_implemented.rpt').read_text('utf-8')
    pairs=[row for row in interactions.splitlines() if 'clk_fpga_1' in row and 'hdmi_clock_wiz' in row]
    assert len(pairs)==2 and all('Asynchronous Groups' in row for row in pairs)
    result['inherited_xdc_parser_warning_review']=json.loads((ROOT/'board_evidence/mode_a_restock_a1/BUILD_WARNING_REVIEW.json').read_text('utf-8'))
    result['hdmi_sys_clock_groups_verified']=True
    (H/'IMPLEMENTATION_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
