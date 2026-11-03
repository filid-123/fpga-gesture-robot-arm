"""Actual three-class Giao programs through PL RAM/DDA/sample handshakes."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from test_mode_b_route_rtl import BENCH
from pc.mode_ab.native_family import trajectory
import numpy as np
def main(out):
 out.mkdir(parents=True,exist_ok=False);records=[];cfg=[];ops=[];gold=[];bindings={};cases=[]
 for name in ('red_cube','eraser','small_canister'):
  path=ROOT/'candidate/mode_ab/native_profiles'/name/'normal.json';c=json.loads(path.read_bytes());p=c['native_program'];bindings[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
  writes=[(0,1),(28,16)];planes=[[r[ch]&0xffffffff for r in p['offsets']] for ch in range(6)]
  descriptors=deep=list(p['descriptors'])
  for i in range(1,len(descriptors),4):
   # The separate production-width timer test covers every T106 hold. This
   # vector sweep covers all 65 positions without repeating multi-second holds.
   descriptors[i]=512 if descriptors[i+1]&(1<<24) else round(descriptors[i]*512/2_000_000)
  planes += [descriptors,p['bases']]
  for plane,values in enumerate(planes):
   writes.append((16,plane))
   for start in range(0,len(values),32):
    writes.append((20,start));writes += [(128+4*i,int(v)&0xffffffff) for i,v in enumerate(values[start:start+32])]
  writes.append((0,2));cfg.extend([len(writes),*[v for a,b in writes for v in (a,b)]])
  operations=[(32,s) for s in range(8)]+[(step,s) for step in range(65) for s in range(8,16)]
  ops.append(len(operations));samples=0
  for step,s in operations:
   data=trajectory(p,s,step);profile=p['descriptors'][(min(2,step//32)*16+s)*4+2]
   ops.extend([(step<<4)|s,len(data),profile,*data[-1].tolist()]);gold.extend(data.reshape(-1).tolist());samples+=len(data)
  cases.append(dict(class_name=name,operations=len(operations),six_axis_samples=samples))
 for name,words in [('cfg.mem',cfg),('ops.mem',ops),('gold.mem',gold)]:
  (out/name).write_text(''.join(f'{int(x)&0xffffffff:08x}\n' for x in words))
 t=BENCH[:BENCH.index('integer b,i,j,k,n;')]
 t=t.replace(".stall_timeout(32'd100)",".stall_timeout(32'd50000000)")
 t+=f'\nreg[31:0] config_words[0:{len(cfg)}],op_words[0:{len(ops)}],gold_words[0:{len(gold)}];\n'
 t+=r'''
integer cp=0,op=0,gp=0,count=0,seen=0,expected=0,profile=0,group_id,base_output;
reg checking=0;reg[191:0]held;reg stalled=0;reg[15:0]lfsr=16'hface;
always @(negedge clk)begin lfsr={lfsr[14:0],lfsr[15]^lfsr[13]^lfsr[12]^lfsr[10]};ready=lfsr[3:0]!=0;end
always @(posedge clk)begin
 if(checking&&sv&&ready&&!pending)begin
  for(integer axis=0;axis<6;axis=axis+1)if(q[axis*32+:32]!==gold_words[gp+axis])$fatal(1,"Native actual vector sample=%d axis=%d actual=%h expected=%h",gp/6,axis,q[axis*32+:32],gold_words[gp+axis]);
  if(spd!==profile[15:0]||acc!==profile[23:16]||grip!==profile[24])$fatal(1,"Native phase profile differs");
  gp=gp+6;seen=seen+1;
 end
 if(stalled&&(!sv||q!==held))$fatal(1,"Native sample changed under downstream backpressure");
 stalled=sv&&!(ready&&!pending);held=q;
end
initial begin
 $readmemh("cfg.mem",config_words);$readmemh("ops.mem",op_words);$readmemh("gold.mem",gold_words);
 repeat(5)@(negedge clk);rst=1;
 for(group_id=0;group_id<3;group_id=group_id+1)begin
  count=config_words[cp];cp=cp+1;
  for(integer j=0;j<count;j=j+1)begin write(config_words[cp],config_words[cp+1],0);cp=cp+2;end
  if(!committed)$fatal(1,"Actual program not committed");
  count=op_words[op];op=op+1;base_output=outputs;
  for(integer j=0;j<count;j=j+1)begin
   @(negedge clk);expected=op_words[op+1];profile=op_words[op+2];seen=0;
   for(integer axis=0;axis<6;axis=axis+1)target[axis*32+:32]=op_words[op+3+axis];
   checking=1;command(7,op_words[op],0);wait(st==4);@(negedge clk);checking=0;
   if(seen!=expected||last!==target)$fatal(1,"Native sample count or phase endpoint differs");op=op+9;
  end
  $display("PASS: real class program %d: %d PL phases, all 65 hand positions, %d backend-accepted vectors",group_id,count,outputs-base_output);
 end
 $finish;
end
initial begin #(64'd2000000000);$fatal(1,"Native vector timeout");end
endmodule
'''
 bench=out/'tb.sv';bench.write_text(t);files=[ROOT/'native_motion/rtl/robot'/n for n in ('b_route_ram.v','b_route_player.v')]+[bench]
 for label,tool,args in [('compile','xvlog',['-sv',*files]),('elaborate','xelab',['tb','-s','native_vectors','-O0','-mt','off']),('run','xsim',['native_vectors','-runall'])]:
  proc=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)],cwd=out,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
  text=(proc.stdout+proc.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text);print(label,proc.returncode,flush=True);records.append(dict(stage=label,exit_code=proc.returncode))
  if proc.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',text):raise RuntimeError(text[-5000:])
 result=dict(passed=True,classes=cases,commands=records,inputs=bindings,checks=[s for s in text.splitlines() if s.startswith('PASS:')],
  test_period_cycles=512,production_period_cycles=2000000,period_ratios_preserved=True,
  timing_scope='T102 motion ratios preserved; T106 holds shortened only in this vector sweep and tested at full production width separately',hardware_access=False,
  source_hashes={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
