"""Actual three-class B tables/FIFO through real S4 RAM, map and hand core.

The transport alone is mocked. Includes the earlier A and B protocol regressions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pc.mode_ab.registers import b_writes,fifo_writes,TASK
from pc.mode_ab.motion import home
from pc.mode_ab.shared_red import compile_path


def replace(s,a,b):
    if s.count(a)!=1:raise ValueError('Harness anchor: '+a)
    return s.replace(a,b)


def main(attempt,native=False):
    out=ROOT/('board_evidence/mode_ab_paths_'+attempt);out.mkdir(exist_ok=False)
    base=ROOT/'board_evidence/mode_ab_task_a7'
    if not json.loads((base/'result.json').read_bytes())['passed']:raise ValueError('Protocol regression must pass first')
    for p in base.glob('*.mem'):shutil.copyfile(p,out/p.name)
    s=(base/'tb_mode_ab.sv').read_text()
    if native:
        s=s.replace('.DYNAMIC_B(1))dut(','.DYNAMIC_B(1),.FAST_B(1))dut(')
        s=s.replace('if(oc==1)begin','''if(oc==1 || oc==7)begin
    if(oc==7 && (!mode_b || dut.mv_prof || !dut.mv_flags[7] || on_a[10:4]>64 || on_a[3:0]>15))$fatal(1,"Native opcode format/legacy collision");
    if(oc==7 && (opf != (dut.mv_kind==1 || dut.mv_kind==2)))$fatal(1,"Native reverse direction was not preserved");''')
        s=s.replace('if(oc==1 && rs','if((oc==1 || oc==7) && rs')
    s=replace(s,'module tb_restock;','''module tb_restock;
reg actual_path=0;
wire amw,amc;wire[3:0]amcell;wire[1:0]amword;wire[31:0]amdata,amrevision;wire[15:0]ammask;
reg[31:0] path_image[0:16383];
''')
    s=replace(s,'.cfg_paths(paths)', '.cfg_paths(actual_path?tables.cfg_paths:paths)')
    s=replace(s,".cfg_home_kp(6'd0),.cfg_predelivery_kp(6'd15)",'.cfg_home_kp(actual_path?tables.cfg_home_kp:6\'d0),.cfg_predelivery_kp(actual_path?tables.cfg_predelivery_kp:6\'d15)')
    s=replace(s,".cfg_t_path_wait(16'd1000)",".cfg_t_path_wait(actual_path?16'd65000:16'd1000)")
    s=replace(s,'lut(.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock)',
              'lut(.clk(clk),.rst_n(rst),.task_active(!dut.cfg_unlock && !(mode_b && dut.fifo_unlock))')
    for a,b in [('cfg_write(mw)','cfg_write(actual_path?amw:mw)'),('cfg_commit(mcommit)','cfg_commit(actual_path?amc:mcommit)'),
                ('cfg_cell(cfgcell)','cfg_cell(actual_path?amcell:cfgcell)'),('cfg_word(cfgword)','cfg_word(actual_path?amword:cfgword)'),
                ('cfg_wdata(mdata)','cfg_wdata(actual_path?amdata:mdata)'),("cfg_revision(32'd1)","cfg_revision(actual_path?amrevision:32'd1)"),
                ("cfg_mask(16'd2)","cfg_mask(actual_path?ammask:16'd2)")]:
        s=replace(s,'.'+a,'.'+b)
    s=replace(s,'.clk(clk),.rst_n(rst),.s_awaddr(axaddr)', '''.map_write(amw),.map_commit(amc),.map_cell(amcell),.map_word(amword),.map_wdata(amdata),.map_revision(amrevision),.map_mask(ammask),
 .map_ready(ready),.map_committed(committed),.map_error(merr),.map_error_code(ec),.map_active_revision(rev),
 .clk(clk),.rst_n(rst),.s_awaddr(axaddr)''')
    tests=[];bindings={};q=[round(v*65536) for v in home('B')]
    packed=''.join(f'{x&0xffffffff:08x}' for x in q[::-1])
    index=0
    for name in ('red_depth12','red_legacy','eraser','small_canister','shared_red'):
        folder=ROOT/'candidate/mode_ab'/('shared_red' if name=='shared_red' else 'profiles/'+name)
        normal=compile_path() if name=='shared_red' else json.loads((folder/'normal.json').read_bytes())
        native_path=ROOT/'candidate/mode_ab/native_profiles'/('red_cube' if name=='red_depth12' else name)/'normal.json'
        if native and name in ('red_depth12','eraser','small_canister'):
            normal=json.loads(native_path.read_bytes());bindings[native_path.relative_to(ROOT).as_posix()]=hashlib.sha256(native_path.read_bytes()).hexdigest()
        for kind in ('normal','restock'):
            path=folder/(kind+'.json')
            if name=='shared_red':
                c=compile_path(restock=kind=='restock')
            else:
                c=normal if native and kind=='normal' else json.loads(path.read_bytes());bindings[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
            rows=b_writes(normal)
            if name=='shared_red' and kind=='restock':
                rows += [[TASK+0x54,0]]
                for bank in range(4):rows += [[TASK+0x12c,bank],[TASK+0x110,0]]+[[TASK+0x114,v] for v in q+[0]*506]
            rows += [r for r in fifo_writes(c,1,1) if r[0]!=TASK]
            words=[len(rows)]+[v for a,b in rows for v in (a-TASK,b)]
            mem=f'path_{index}.mem';(out/mem).write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words))
            tests.append(f'''
 actual_path=0;reset_all();actual_path=1;image_y=64;scenario={800+index};
 @(negedge clk);last=192'h{packed};target=last;km_home=last;
 write_cfg(12'h024,1);b_select();cmd(9);$readmemh("{mem}",path_image);
 for(integer z=0;z<path_image[0];z=z+1)write_cfg(path_image[1+z*2],path_image[2+z*2]);
 repeat(30)@(negedge clk);if(merr || !committed)$fatal(1,"Dynamic B map was not committed in WAIT_PATH");
 b_commit();gesture(4,1,1);wait({'restocks' if kind=='restock' else 'dones'}==1 || fl);wait(status[3:0]==1 || fl);repeat(8)@(negedge clk);
 if(fl || last!==km_home || status[28:26]!=7 || cancels!=0)$fatal(1,"Actual {name} {kind} path failed %h",fault);
 $display("PASS: actual {name} {kind} table/FIFO/map commits and completes at low HOME");
''')
            index+=1
            if native and kind=='normal' and name in ('red_depth12','eraser','small_canister'):
                openq=c['fifo'][2]['target_q16'];source=''.join(f'{x&0xffffffff:08x}' for x in openq[::-1])
                tests.append(f'''
 actual_path=0;reset_all();actual_path=1;image_y=64;scenario={900+index};out_cycles=64000;
 @(negedge clk);last=192'h{packed};target=last;km_home=last;slot_open[1]=192'h{source};
 write_cfg(12'h024,1);b_select();cmd(9);$readmemh("{mem}",path_image);
 for(integer z=0;z<path_image[0];z=z+1)write_cfg(path_image[1+z*2],path_image[2+z*2]);
 repeat(30)@(negedge clk);b_commit();
 wait(dut.holding && dut.mv_active && dut.mv_na[3:0]==4 || fl);
 if(fl)$fatal(1,"Native cancel never reached LIFT");gesture(5,1,1);wait(dut.cancel_req || fl);gesture(0,1,0);
 wait(status[3:0]==1 || fl);repeat(8)@(negedge clk);
 if(fl || last!==km_home || cancels!=1 || dones!=0 || status[9])$fatal(1,"Native partial FIST return failed %h",fault);
 $display("PASS: native {name} partial FIST returns HOME with reverse opcode and original-slot release");
''')
    tests.append(r'''
 write_cfg(12'h000,4096);repeat(3)@(negedge clk);if(tables.cmd_index!=12)$fatal(1,"Shared red CONTROL bit12 was not decoded");
 req=1;base_moves=moves;cmd(12);repeat(6)@(negedge clk);
 if(status[28:26]!=6 || moves!=base_moves)$fatal(1,"Shared red empty changes the wrong inventory or moves");
 cmd(11);repeat(6)@(negedge clk);if(status[28:26]!=7)$fatal(1,"Shared red B-mode restock acknowledgement failed");
 req=2;@(negedge clk);ci=12;cv=1;@(negedge clk);cv=0;wait(cd);if(cr!=2)$fatal(1,"Shared red command changed another slot");@(negedge clk);
 if(status[28:26]!=7 || moves!=base_moves)$fatal(1,"Non-red inventory changed");
 $display("PASS: shared red empty/refill works in B IDLE, preserves other stocks and never starts a MOVE");
''')
    s=replace(s,' $fclose(trace);$finish;','\n'.join(tests)+'\n $fclose(trace);$finish;')
    bench=out/'tb.sv';bench.write_text(s)
    files=[ROOT/'native_motion/rtl/robot'/n for n in ('s4_task_fsm.v','s4_task_regs.v','hand_align_region_lut.v','hand_align_target_core.v')]+[bench]
    records=[]
    for label,tool,args in [('compile','xvlog',['-sv',*files]),('elaborate','xelab',['tb_restock','-s','paths','-O0','-mt','off']),('run','xsim',['paths','-runall'])]:
        cmd=['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)]
        p=subprocess.run(cmd,cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=600)
        text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text)
        print(label,p.returncode,flush=True);records.append(dict(stage=label,exit_code=p.returncode))
        if p.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-4500:])
    checks=[x for x in text.splitlines() if x.startswith('PASS:')]
    if len(checks)!=(28 if native else 25):raise ValueError('Expected all production scenarios')
    (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,commands=records,inputs=bindings,
        sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        motion_transport='MOCK',physical_execution=False),indent=2))
    print('\n'.join(checks))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--native',action='store_true');a=p.parse_args();main(a.attempt,a.native)
