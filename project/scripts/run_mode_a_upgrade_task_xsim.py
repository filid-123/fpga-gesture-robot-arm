"""Continuous-coordinate S4/core regressions; motion transport is explicitly mocked."""
from pathlib import Path
import argparse,json,re,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]
def main(attempt):
 out=ROOT/('board_evidence/mode_a_upgrade_task_'+attempt);out.mkdir(parents=True,exist_ok=False)
 candidate=ROOT/'candidate/S4_BANKED_CANDIDATE.json'
 if not candidate.exists():candidate=ROOT/'board_evidence/mode_a_upgrade_plan_a3/S4_BANKED_CANDIDATE.json'
 t=json.loads(candidate.read_text('utf-8'))
 words=[]
 for b in t['keypoint_banks']:
  a=[v for q in b for v in q+[0,0]];words+=a+[0]*(512-len(a))
 (out/'keypoints.mem').write_text(''.join(f'{v&0xffffffff:08x}\n' for v in words))
 (out/'segments.mem').write_text(''.join(f'{v:08x}\n' for kp,n,na,p,f in t['segments'] for v in ((f<<24)|(p<<16)|kp,(na<<16)|n)))
 (out/'pair_timing.mem').write_text(''.join(f"{((p['na']<<16)|p['n']):08x}\n" for p in t['align_pairs']))
 s=(ROOT/'native_motion/sim/mode_a_follow/tb_s4_four.sv').read_text()
 s=s.replace('always @(posedge clk)begin kd<=km[kbank*512+ka];sd<=sm[sa];end','''wire[6:0]active_step;reg[6:0]target_step=32;wire mix;
 reg[31:0]kd0,kd1,kd2;integer lb,wt;reg signed[63:0]loq,hiq,mixq;
 always @(posedge clk)begin
  if(freq && image_x<128 && image_y>=16 && image_y<=111)begin
   if(image_y<=44)target_step<=64;else if(image_y>=84)target_step<=0;else target_step<=((84-image_y)*8+2)/5;
  end
  lb=(active_step<32)?0:1;wt=(active_step<32)?active_step:active_step-32;
  loq=$signed(km[lb*512+ka]);hiq=$signed(km[(lb+1)*512+ka]);mixq=loq+(((hiq-loq)*wt+16)>>>5);
  kd0<=mix?mixq[31:0]:km[kbank*512+ka];kd1<=kd0;kd2<=kd1;kd<=kd2;sd<=sm[sa];
 end''')
 start=s.index(' always @(posedge clk)begin\n  if(freq');end=s.index('\n end',start)+5;block=s[start:end];s=s[:start]+s[end:];marker='always @(posedge clk)if(freq)frameid<=frameid+1;';s=s.replace(marker,marker+'\n'+block)
 s=s.replace('.HAND_ALIGN_LOCATOR(1))dut(', '.HAND_ALIGN_LOCATOR(1),.CONTINUOUS_HAND(1))dut(\n .align_target_step(target_step),.active_step(active_step),.kp_mix_enable(mix),')
 s=s.replace('.EXPLICIT_ACCEPT(1)) hc', '.EXPLICIT_ACCEPT(1),.PIPELINED_FRESHNESS(1)) hc')
 s=s.replace('.cfg_arrival_mask(6\'h3f)', '.cfg_arrival_mask(6\'h00)')
 s=s.replace('.cfg_mask(16\'d7)', '.cfg_mask(16\'d2)')
 s=s.replace('for(integer c=0;c<3;c=c+1)', 'for(integer c=1;c<2;c=c+1)').replace('1:case(c)0:mdata=74|(111<<9);1:mdata=54|(73<<9);2:mdata=16|(53<<9);endcase','1:mdata=16|(111<<9);')
 s=s.replace('bank_case<3','bank_case<5').replace('image_y=(bank_case==0)?86:((bank_case==1)?64:44)', 'image_y=84-bank_case*10')
 s=s.replace('dut.active_bank==bank_case', 'active_step==bank_case*16').replace('lcell!=bank_case','lcell!=1')
 s=s.replace('dut.active_bank==2 && pauses>0', 'active_step==64 && pauses>0')
 keys=[f'{ph}_{o}' for ph in ('approach','grasp','lift') for o in (1,2,3)]+['deliver','release','retreat']
 for i,key in enumerate(keys):
  first,count=t['descriptors'][key];s=re.sub(r'paths\['+str(i*12)+r'\+:12\]=.*?;',f"paths[{i*12}+:12]={{6'd{count},6'd{first}}};",s)
 d=lambda k:(t['descriptors'][k][1]<<6)|t['descriptors'][k][0]
 s=s.replace("mdata=(15)|(12'd557<<6)|(12'd97<<18)",f"mdata=32'd{t['predelivery_kp']|(d('release')<<6)|(d('deliver')<<18)}").replace("mdata=12'd353",f"mdata=32'd{d('retreat')}")
 s=s.replace('all three active banks','five continuous positions (0/16/32/48/64)').replace('Y-bank','continuous Y').replace('region PAUSE','coordinate PAUSE')
 bench=out/'tb_continuous_task.sv';bench.write_text(s)
 files=[ROOT/'native_motion/rtl/robot'/n for n in ('s4_task_fsm.v','hand_align_target_core.v','hand_align_region_lut.v')]+[bench]
 records=[]
 for label,tool,args in [('compile','xvlog',['-sv',*map(str,files)]),('elab','xelab',['tb_s4_handalign','-s','task','-O0','-mt','off']),('run','xsim',['task','-runall'])]:
  r=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*args],cwd=out,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  txt=(r.stdout+r.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(txt);print(label,r.returncode,flush=True)
  records.append(dict(label=label,exit_code=r.returncode))
  if r.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:)',txt):raise RuntimeError(txt[-4000:])
 checks=[x for x in txt.splitlines() if x.startswith('PASS:')];assert len(checks)==7
 (out/'RESULT.json').write_text(json.dumps(dict(passed=True,checks=checks,motion_link='MOCK',keypoint_interpolation='INDEPENDENT_BENCH_REFERENCE; production RAM verified separately',physical_robot=False,commands=records,source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2)+'\n')
 print('\n'.join(checks))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);main(ap.parse_args().attempt)
