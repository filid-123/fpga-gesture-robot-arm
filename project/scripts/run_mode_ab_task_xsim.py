"""Production S4 RAM/FSM with A regression plus dynamic B protocol scenarios.

Motion transport is mocked. No physical or UART timing acceptance is inferred.
The original A harness supplies its independently checked memory vectors.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Harness anchor changed: '+before[:90])
    return text.replace(before, after)


def main(attempt):
    out = ROOT/('board_evidence/mode_ab_task_'+attempt)
    out.mkdir(parents=True, exist_ok=False)
    fixture = ROOT/'board_evidence/mode_a_restock_task_ab_legacy_a1'
    if not json.loads((fixture/'RESULT.json').read_text('utf-8'))['passed']:
        raise ValueError('Actual A regression fixture required')
    for path in fixture.glob('*.mem'):
        shutil.copyfile(path, out/path.name)
    t = json.loads((ROOT/'candidate/S4_BANKED_CANDIDATE.json').read_text('utf-8'))
    rs = json.loads((ROOT/'candidate/restock/S4_RESTOCK_CANDIDATE.json').read_text('utf-8'))
    def vectors(segments, points):
        return [v for kp,n,na,profile,flags in segments
                for v in points[kp]+[(flags<<24)|(profile<<16),(na<<16)|n]]
    normal = []
    for key in ('approach_1','grasp_1','lift_1'):
        first,count = t['descriptors'][key]
        normal.extend(t['segments'][first:first+count])
    restored = []
    for d in (rs['prefix'], rs['tails'][0]):
        restored.extend(rs['segments'][d['first']:d['first']+d['count']])
    release = next(i for i,row in enumerate(restored) if row[0] == rs['tails'][0]['release_kp'])
    for name, words in [('b_normal.mem', vectors(normal, t['keypoint_banks'][1])),
                        ('b_restock.mem', vectors(restored, rs['keypoints']))]:
        (out/name).write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words), encoding='ascii')
    template = ROOT/'native_motion/sim/mode_a_restock/tb_restock.sv'
    s = template.read_text('utf-8')
    s = once(s, 'module tb_restock;', '''module tb_restock;
wire mode_b;wire[8:0]b_faddr;wire[31:0]b_fdata;wire[5:0]b_fcount;wire b_clear;
wire b_kind;wire[5:0]b_release;wire[15:0]b_selected,b_path_id;wire[1:0]b_object;
reg[31:0]bn[0:511],br[0:511];integer bn_count=BN_COUNT,br_count=BR_COUNT;
'''.replace('BN_COUNT',str(len(normal))).replace('BR_COUNT',str(len(restored))))
    s = once(s, '.AUTO_RESTOCK(1))dut(', '.AUTO_RESTOCK(1),.DYNAMIC_B(1))dut(\n .cfg_b_restock(b_kind),.cfg_b_release_index(b_release),.selected_task_id(b_selected),')
    s = once(s, ".cfg_mode_b(1'b0)", '.cfg_mode_b(mode_b)')
    s = once(s, ".path_object(2'd0),.path_task_id(16'd0)", '.path_object(b_object),.path_task_id(b_path_id)')
    s = once(s, ".fifo_rdata(32'd0),.fifo_count(6'd0)", '.fifo_rdata(b_fdata),.fifo_count(b_fcount),.fifo_raddr(b_faddr),.fifo_clear(b_clear)')
    s = once(s, 'if(rs && status[26+dut.object-1])', 'if(rs && !mode_b && status[26+dut.object-1])')
    s = once(s, 'dut.sp>23', 'dut.sp>(mode_b?63:23)')
    s = once(s, '.CONTINUOUS_HAND(1))tables(', '.CONTINUOUS_HAND(1),.DYNAMIC_B(1))tables(\n .cfg_mode_b(mode_b),.cfg_b_restock(b_kind),.cfg_b_release_index(b_release),.selected_task_id(b_selected),.path_object(b_object),.path_task_id(b_path_id),.status_word(status),.fifo_raddr(b_faddr),.fifo_rdata(b_fdata),.fifo_count(b_fcount),')
    s = once(s, ".fifo_clear(1'b0)", '.fifo_clear(b_clear)')
    helpers = r'''
task b_select;
 begin gesture(0,1,0);wait_ticks(3);gesture(1,1,0);wait(status[3:0]==2 || fl);if(fl)$fatal(1,"B select fault");end
endtask
task b_upload(input integer kind,input integer bad_index);
 begin
  cmd(9);
  write_cfg(12'h38c,kind | ((bad_index>=0?bad_index:RELEASE_INDEX)<<8));
  for(integer z=0;z<(kind?br_count:bn_count)*8;z=z+1)write_cfg(12'h068,kind?br[z]:bn[z]);
  if(b_fcount!==(kind?br_count:bn_count))$fatal(1,"FIFO incomplete");
  write_cfg(12'h05c,(b_selected<<16)|1);
 end
endtask
task b_commit;
 begin cmd(8);wait(status[3:0]==4 || status[3:0]==1 || fl);if(fl || status[3:0]!=4)$fatal(1,"B commit refused %h",fault);end
endtask
task rejected_commit;
 begin @(negedge clk);ci=8;cv=1;@(negedge clk);cv=0;wait(cd);if(cr!=2)$fatal(1,"Stale B task identity accepted");@(negedge clk);end
endtask
'''.replace('RELEASE_INDEX',str(release))
    s = once(s, 'initial begin\n trace=', helpers+'\ninitial begin\n trace=')
    s = once(s, '$readmemh("keypoints.mem",km);', '$readmemh("b_normal.mem",bn);$readmemh("b_restock.mem",br);\n $readmemh("keypoints.mem",km);')
    tests = r'''
 reset_all();image_y=64;scenario=600;write_cfg(12'h024,1);b_select();
 read_cfg(12'h390,32'h00010001);base_moves=moves;
 // Path table mutation is permitted at the stationary WAIT_PATH boundary.
 write_cfg(12'h12c,3);write_cfg(12'h110,511);write_cfg(12'h114,32'h12345678);
 repeat(2)@(negedge clk);
 if(tables.kp_mem[2047]!==32'h12345678)$fatal(1,"WAIT_PATH table write rejected");
 // Mode and joint envelopes must remain locked at that same boundary.
 write_cfg(12'h024,0);if(!mode_b)$fatal(1,"WAIT_PATH mode write accepted");
 write_cfg(12'h080,32'h55555555);if(tables.cfg_joint_min[31:0]!==32'h80000000)$fatal(1,"WAIT_PATH limit write accepted");
 b_upload(0,-1);write_cfg(12'h05c,1);rejected_commit();
 if(moves!=base_moves || status[3:0]!=2)$fatal(1,"Old task moved");
 write_cfg(12'h05c,(b_selected<<16)|1);cmd(8);
 write_cfg(12'h12c,2);write_cfg(12'h068,32'hfeedbeef);
 if(tables.cfg_bank!=3 || b_fcount!=bn_count)$fatal(1,"COMMIT scan is not immutable");
 gesture(4,1,1);wait(dones==1 || fl);wait(status[3:0]==1 || fl);
 if(fl || last!==km_home || status[28:26]!=7)$fatal(1,"B normal completion changed A inventory/home");
 $display("PASS: dynamic B WAIT_PATH-only tables, immutable COMMIT scan, selected task identity and real PALM/core completion");

 gesture(0,1,0);wait_ticks(3);b_select();if(b_selected!=2)$fatal(1,"B selection sequence not advanced");
 cmd(3);wait(status[3:0]==1);b_select();if(b_selected!=3)$fatal(1,"Cancelled WAIT_PATH reused task identity");
 b_upload(0,-1);write_cfg(12'h05c,(16'd2<<16)|1);rejected_commit();cmd(3);wait(status[3:0]==1);
 $display("PASS: cancelled or timed-out B selections cannot accept an earlier task path");

 reset_all();image_y=64;scenario=700;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(restocks==1 || fl);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || last!==km_home || status[28:26]!=7 || dones!=0)$fatal(1,"B dynamic restock completion failed");
 base_moves=moves;wait_ticks(100);if(moves!=base_moves)$fatal(1,"Held B digit retriggered");
 $display("PASS: dynamic B restock uses FIFO end-to-end without PALM and preserves separate A inventory");

 reset_all();image_y=64;scenario=701;stretch_pos=11;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(rs && dut.holding && dut.pos==stretch_pos && busy>0);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || cancels!=1 || restocks!=0 || last!==km_home || status[28:26]!=7)$fatal(1,"B restock cancel failed");
 $display("PASS: dynamic B held restock drains and retraces its actual public pickup before HOME");

 reset_all();image_y=64;scenario=702;stretch_pos=RELEASE_POS;write_cfg(12'h024,1);b_select();b_upload(1,-1);b_commit();
 wait(rs && dut.released && busy>0);gesture(5,1,0);wait(restocks==1 || fl);wait(status[3:0]==1 || fl);
 if(fl || cancels!=0 || last!==km_home)$fatal(1,"B restock release commitment reversed");
 $display("PASS: dynamic B placement opening is a commitment; later FIST completes retreat/HOME");

 reset_all();image_y=64;scenario=703;write_cfg(12'h024,1);b_select();b_upload(1,31);base_moves=moves;cmd(8);
 wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || moves!=base_moves || restocks!=0)$fatal(1,"B missing release accepted");
 $display("PASS: malformed dynamic B restock release index is refused before any MOVE");

 reset_all();image_y=64;scenario=704;write_cfg(12'h024,1);b_select();cmd(9);
 // Forty repeated safe endpoint segments cross the old 32-entry address boundary.
 for(integer z=0;z<40;z=z+1)
  for(integer w=0;w<8;w=w+1)write_cfg(12'h068,bn[w]);
 for(integer z=8;z<bn_count*8;z=z+1)write_cfg(12'h068,bn[z]);
 write_cfg(12'h05c,(b_selected<<16)|1);b_commit();
 wait(dut.sp>32);gesture(5,1,0);wait(status[3:0]==1 || fl);repeat(6)@(negedge clk);
 if(fl || cancels!=1 || last!==km_home)$fatal(1,"Extended FIFO/stack did not retrace to HOME");
 b_select();cmd(9);
 for(integer z=0;z<64*8;z=z+1)write_cfg(12'h068,bn[z%8]);
 if(b_fcount!=63 || !tables.fifo_overflow)$fatal(1,"FIFO capacity overflow wrapped count or was not rejected");
 cmd(3);wait(status[3:0]==1);
 $display("PASS: B FIFO/return stack crosses entry 32 and rejects the 64th segment without wrap");
'''.replace('RELEASE_POS',str(release+1))
    s = once(s, ' $fclose(trace);$finish;', tests+'\n $fclose(trace);$finish;')
    bench = out/'tb_mode_ab.sv'
    bench.write_text(s, encoding='utf-8')
    files = [ROOT/'native_motion/rtl/robot'/name for name in
             ('s4_task_fsm.v','s4_task_regs.v','hand_align_region_lut.v','hand_align_target_core.v')]+[bench]
    records = []
    for label,tool,args in [('compile','xvlog',['-sv',*files]),('elab','xelab',['tb_restock','-s','ab','-O0','-mt','off']),('run','xsim',['ab','-runall'])]:
        tokens = list(map(str, ['E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args]))
        cmd = 'cmd.exe /d /s /c "'+' '.join('"'+v+'"' for v in tokens)+'"'
        result = subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
        text = (result.stdout+result.stderr).decode('utf-8',errors='replace')
        (out/(label+'.txt')).write_text(text,encoding='utf-8')
        print(label,result.returncode,flush=True)
        records.append(dict(label=label,command=cmd,exit_code=result.returncode))
        if result.returncode or re.search(r'^(ERROR:|FATAL:|Fatal:|FAIL:)',text,re.M):
            raise RuntimeError(text[-5000:])
    checks = [line for line in text.splitlines() if line.startswith('PASS:')]
    if len(checks) != 14:
        raise ValueError('Expected seven original A and six B scenarios')
    report = dict(passed=True,checks=checks,commands=records,physical_test='NOT_RUN',motion_transport='MOCK',
                  keypoint_and_fifo_memory='PRODUCTION_S4_REGS',
                  source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('\n'.join(checks))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True)
    main(p.parse_args().attempt)
