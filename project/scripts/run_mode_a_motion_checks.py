"""Run real XSim: existing independent S4 golden traces plus inventory checks."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

W=Path(__file__).resolve().parents[1]
TOOLS=Path('E:/Xilinx/2026.1/Vivado/bin')


def main(attempt=None,timed=False,handover=False):
    attempt=attempt or (sys.argv[1] if len(sys.argv)>1 else 'a1')
    if not re.fullmatch('a[0-9]+',attempt):raise ValueError(attempt)
    prefix='mode_a_handover_integration_' if handover else ('mode_a_board_integration_' if timed else 'mode_a_motion_20261027_')
    out=W/'board_evidence'/(prefix+attempt)
    out.mkdir(parents=True,exist_ok=False)
    build=W/'runs'/((prefix if timed else 'mode_a_motion_')+attempt);build.mkdir(parents=True,exist_ok=False)
    rtl=W/'native_motion/rtl/robot';tb=W/'native_motion/sim/phase3_robot/rtl'
    body=(tb/'tb_s4_task_body.vh').read_text('utf-8')
    body=body.replace('.VIS_ASYNC(VISA))','.VIS_ASYNC(VISA), .SLOT_INVENTORY(1))')
    body=body.replace("32'h0000_3403","32'h0000_3404")
    if timed:
        body=body.replace('.SLOT_INVENTORY(1))','.SLOT_INVENTORY(1), .TIMED_WALKTHROUGH(1))').replace("32'h0000_3404","32'h0000_3405")
        # COMM fault remains required, but removing arrival waits can issue an
        # extra MOVE before the same feedback deadline. Its old timed trace is
        # inapplicable. Keep full fault/counter/post-fault-gating assertions;
        # normal DRY_RUN/LINE scenarios retain exact action and S2 sample oracles.
        body=body.replace('if (chk_p >= 0 && act_n > chk_n)', 'if (SCEN!=7 && chk_p >= 0 && act_n > chk_n)')
        body=body.replace('&& act_n == n_act_exp &&', '&& (SCEN==7 || act_n == n_act_exp) &&')
        body=body.replace('        // ---- action trace\n','        // ---- action trace\n        if (SCEN!=7) begin\n')
        body=body.replace('        // ---- final registers\n','        end\n        // ---- final registers\n')
        body=body.replace('        $display("PASS: tb_s4 scenario', '        if (SCEN==7) $display("PASS: timed COMM final fault/counters and postfault sample cutoff; arrival-dependent legacy action timing excluded");\n        else $display("PASS: tb_s4 scenario')
    if handover:
        body=body.replace('.TIMED_WALKTHROUGH(1))','.TIMED_WALKTHROUGH(1),.HANDOVER_V2(1))').replace("32'h0000_3405","32'h0000_3406")
        body=body.replace('if (flags[1]) begin',"if (1'b0) begin")  # real external vision port, not PS injection
        body=body.replace('reg fist_done, estop_done', 'reg blind_drop=0;reg fist_done, estop_done')
        body=body.replace("            if (dut.u_fsm.st == 4'd5) begin","            if((SCEN==0 || SCEN==1) && !blind_drop && dut.u_fsm.ph==2 && dut.u_fsm.st==4)begin blind_drop=1;set_vision(3'd7,1'b0);end\n            if (dut.u_fsm.st == 4'd5) begin")
        body=body.replace('s4_cmd(0, 0);',"axi_write(3,12'h124,100,RESP_OKAY);axi_write(3,12'h128,10,RESP_OKAY);axi_read(3,12'h124,v);if(v!=100)$fatal(1,\"FIST timer readback\");axi_read(3,12'h128,v);if(v!=10)$fatal(1,\"PRE timer readback\");axi_read(3,12'h260,v);axi_read(3,12'h264,v);s4_cmd(0, 0);")
        body=body.replace('g[sp_s4 + 2 + 2 * i], RESP_OKAY);',"((g[sp_s4 + 1 + 2 * i][11:0]==12'h024)?(g[sp_s4 + 2 + 2 * i]&32'hfffffff7):g[sp_s4 + 2 + 2 * i]), RESP_OKAY);")
    body=body.replace('s4_cmd(0, 0);', '''
            axi_read(3,R_STATUS,v);
            if (v[28:26]!==3'b000) $fatal(1,"FAIL: unexpected initial inventory");
            axi_write(3,12'h058,{16'd0,14'd0,obj[1:0]},RESP_OKAY);
            s4_cmd(11,0); // explicit operator-confirmed refill, no motion
            axi_read(3,R_STATUS,v);
            if (!v[26+obj-1]) $fatal(1,"FAIL: restock did not publish inventory");
            s4_cmd(0, 0);''')
    body=body.replace('        $display("PASS: tb_s4 scenario', '''
        axi_read(3,R_STATUS,v);
        if (exp_done && v[26+obj-1]) $fatal(1,"FAIL: delivered slot still stocked");
        if (exp_cancel && !v[26+obj-1]) $fatal(1,"FAIL: returned slot not restored");
        if (exp_done) begin
            axi_write(3,12'h058,{16'd0,14'd0,obj[1:0]},RESP_OKAY);
            s4_cmd(2,2); // empty slot refused without movement
            axi_read(3,R_FAULT,v);
            if(v[23:16]!=11) $fatal(1,"FAIL: missing EMPTY_SLOT refusal");
            s4_cmd(11,0);
            axi_read(3,R_STATUS,v);
            if (!v[26+obj-1]) $fatal(1,"FAIL: explicit refill after delivery");
        end
        $display("PASS: tb_s4 scenario''')
    (out/'tb_inventory_body.vh').write_text(body,'utf-8')
    benches=[]
    names=['tb_s4_a_happy','tb_s4_a_line_happy','tb_s4_a_fault_comm','tb_s4_a_fault_estop'] if timed else ['tb_s4_a_happy','tb_s4_a_cancel_approach','tb_s4_a_cancel_holding','tb_s4_a_fault_arrival','tb_s4_a_fault_comm','tb_s4_a_fault_estop']
    for name in names:
        text=(tb/(name+'.v')).read_text('utf-8')
        if handover:text='`define TB_S4_TRACE\n'+text.replace('VISA = 0','VISA = 1')
        target=name.replace('tb_s4_','tb_inventory_')
        p=out/(target+'.v')
        p.write_text(text.replace(name,target).replace('tb_s4_task_body.vh','tb_inventory_body.vh'),'utf-8')
        benches.append(p)
    golden=W/'native_motion/sim/phase3_robot/golden'
    shutil.copytree(golden,build/'sim/phase3_robot/golden')
    commands=[]
    def run(label,tool,args):
        tokens=[str(TOOLS/(tool+'.bat')),*map(str,args)]
        if any(re.search(r'["%!^&|<>]',t) for t in tokens):raise ValueError(tokens)
        command='cmd.exe /d /s /c "'+' '.join('"'+x+'"' for x in tokens)+'"'
        p=subprocess.run(command,cwd=build,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                         timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(label+'.txt')).write_bytes(p.stdout)
        text=p.stdout.decode('utf-8',errors='replace')
        commands.append(dict(label=label,command=command,exit_code=p.returncode,
                             sha256=hashlib.sha256(p.stdout).hexdigest()))
        (out/'COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n','utf-8')
        if p.returncode or re.search(r'^\s*(ERROR:|Error:|Fatal:|FATAL:|FAIL:)',text,re.M):
            raise ValueError(label+': '+text[-2000:])
        if tool=='xsim' and not re.search(r'^PASS:',text,re.M):raise ValueError('Missing PASS '+label)
        if any(s in text.lower() for s in ['cannot open','cannot be opened','failed to open']):raise ValueError('Missing input '+label)
        print('PASS '+label,flush=True)
    files=[*rtl.glob('*.v'),*benches]
    f=out/'compile.f';f.write_text('\n'.join(p.as_posix() for p in files)+'\n','utf-8')
    run('compile','xvlog',['-sv','-i',out,'-i',tb,'-f',f])
    for p in benches:
        run(p.stem+'_elab','xelab',[p.stem,'-s',p.stem,'-O0','-mt','off'])
        run(p.stem,'xsim',[p.stem,'-runall'])
    (out/'RESULT.json').write_text(json.dumps(dict(passed=True,actual_xsim_runs=len(benches),
        sources={p.relative_to(W).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in rtl.glob('*.v')},
        tests=('ABI3406 external qualified vision, timer readbacks and telemetry, exact normal DRY_RUN/LINE/S2 samples, inventory, COMM/D5' if handover else 'ABI3405 exact normal DRY_RUN/LINE actions and S2 samples, inventory, D5; COMM fault/counters/post-fault gating without the obsolete arrival-dependent trace' if timed else 'independent full S4 action and exact S2 sample golden plus reset/refill/empty/delivery/cancel inventory'),
        physical_hardware=False),indent=2)+'\n','utf-8')


if __name__=='__main__':main()
