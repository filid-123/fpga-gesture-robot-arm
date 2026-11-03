"""Offline v2 model integration: exact TRAIN fixtures, RTL and source binding. No hardware."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,re,shutil,subprocess,time,sys
import numpy as np
import cv2
W=Path(__file__).resolve().parent.parent
PKG=W/'model_package/candidates/black_scene_vision_v2_int8_B_gate030_20261024'
R=Path('D:/FPGA_Projects/Gesture')
H=R/'board_evidence/mode_a_black_scene_v2_20261024_v0_3_0'
TOOLS=Path('E:/Xilinx/2026.1/Vivado/bin')
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ATTEMPT='a1'

def source_list():
 text=(W/'native_motion/scripts/create_roarm_closed_loop_project.tcl').read_text('utf-8')
 return [W/'native_motion/rtl'/v for key in ('s3_sources','motion_sources','s5_sources') for v in re.search('set '+key+r' \{(.*?)\}',text,re.S).group(1).split()]

def prepare():
 idx=json.loads((PKG/'golden_integer/index.json').read_text('utf-8'))['samples']
 folder=H/'fixtures';folder.mkdir(exist_ok=True);assert not any(folder.iterdir());rows=[]
 for i,item in enumerate(idx):
  a=np.load(PKG/item['vectors'],allow_pickle=False);small=a['locator_input_u8'].reshape(128,128);src=cv2.cvtColor(cv2.imread(str(PKG/item['image'])),cv2.COLOR_BGR2GRAY)
  assert src.shape==(480,640) and small.shape==(128,128)
  expected=np.zeros((128,128),np.uint8);expected[16:112]=src[::5,::5];assert np.array_equal(expected,small)
  for name,image in [('source',src),('small',small)]:
   words=np.frombuffer(image.tobytes(),dtype='<u4');(folder/f'{i:02d}_{name}.mem').write_text(''.join(f'{int(v):08x}\n' for v in words),encoding='ascii',newline='\n')
  rows.append(dict(index=i,sample=item['id'],expected=item['pipeline'],small_sha256=hashlib.sha256(small.tobytes()).hexdigest()))
 palm=next(i for i,x in enumerate(idx) if x['class_label']=='palm' and x['pipeline']['classifier']['class']=='palm')
 shutil.copyfile(folder/f'{palm:02d}_source.mem',folder/'palm_source.mem')
 shutil.copyfile(PKG/'golden_integer'/idx[palm]['id']/'classifier_input_u8.mem',folder/'palm_roi.mem')
 files=source_list();model=[PKG/'quantized'/p for p in ('locator/model_rom_16k.mem','classifier/weights_all.mem','classifier/layer_descriptors.mem')]
 previous=W/'model_package/candidates/black_scene_vision_v1_int8_20261013'
 assert (previous/'quantized/locator/model_rom_16k.bin').read_bytes()==(PKG/'quantized/locator/model_rom_16k.bin').read_bytes()
 old=dict(np.load(previous/'quantized/locator/parameters.npz',allow_pickle=False));new=dict(np.load(PKG/'quantized/locator/parameters.npz',allow_pickle=False))
 assert set(old)==set(new) and [k for k in old if not np.array_equal(old[k],new[k])]==['confidence_threshold_i32']
 result=dict(status='PASS_INPUT_AND_CONTRACT_BINDING',samples=rows,source_files=len(files),rtl_hashes={p.relative_to(W).as_posix():SHA(p) for p in files},model_hashes={p.relative_to(W).as_posix():SHA(p) for p in model},fixture_hashes={p.name:SHA(p) for p in folder.glob('*.mem')},final_top_palm_sample=idx[palm]['id'],locator_ROM_identical=True,only_locator_parameter_change='confidence_threshold_i32')
 (H/'INPUT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('PASS:26 exact VGA/Gray8->Phase2 B fixtures and protected locator binding',flush=True)

class Job:
 def __init__(self,name):
  self.b=R/'runs'/('black_scene_v2_'+name+'_'+ATTEMPT);self.o=H/('rtl_'+name+'_'+ATTEMPT);self.b.mkdir(exist_ok=False);self.o.mkdir(exist_ok=False);self.commands=[]
  a=json.loads((H/'INPUT_AUDIT.json').read_text('utf-8'))
  for rel,v in a['rtl_hashes'].items():assert SHA(W/rel)==v,rel
  for rel,v in a['model_hashes'].items():assert SHA(W/rel)==v,rel
  for rel in [*a['model_hashes'],'native_motion/geometry_alpha_q16.mem','native_motion/rtl/autonomous/ov5640_vga_yuyv.mem','native_motion/sim/black_scene/generated/geometry_cases.mem','native_motion/sim/black_scene/generated/geometry_ema_cases.mem']:
   p=self.b/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(W/rel,p)
  if name in ('classifier','locator'):
   for source in (PKG/'golden_integer').glob('sample_*/*.mem'):
    dst=self.b/source.relative_to(W);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dst)
 def run(self,label,tool,args):
  tokens=list(map(str,[TOOLS/(tool+'.bat'),*args]));assert not any(re.search(r'["%!^&|<>]',x) for x in tokens)
  command='cmd.exe /d /s /c "'+' '.join('"'+x+'"' for x in tokens)+'"';start=time.monotonic()
  r=subprocess.run(command,cwd=self.b,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW);txt=r.stdout.decode('utf-8',errors='replace');(self.o/(label+'.txt')).write_bytes(r.stdout)
  row=dict(label=label,command=command,exit_code=r.returncode,wall_s=round(time.monotonic()-start,3),sha256=hashlib.sha256(r.stdout).hexdigest());self.commands.append(row);(self.o/'COMMANDS.json').write_text(json.dumps(self.commands,indent=2)+'\n');print(json.dumps(row),flush=True)
  assert r.returncode==0 and not re.search(r'^\s*(ERROR:|Error:|FATAL:|Fatal:|FAIL:)',txt,re.M),label
  assert not any(x in txt.lower() for x in ('cannot open','cannot be opened','failed to open','could not open')),label
  return txt
 def compile(self,benches):
  files=[*source_list(),*[W/p for p in benches]];f=self.b/'compile.f';f.write_text('\n'.join(p.as_posix() for p in files)+'\n');self.run('compile','xvlog',['-sv','-i',W/'native_motion/rtl/autonomous','-f',f])
 def simulate(self,top,args=()):
  self.run(top+'_elab','xelab',[top,'-s',top,'-O0','-mt','off']);txt=self.run(top+'_run','xsim',[top,'-runall',*args]);assert re.search(r'^PASS:',txt,re.M),top;return txt

def pipeline_worker(worker):
 j=Job('pipeline'+str(worker));j.compile(['native_motion/sim/black_scene_v2/tb_pipeline_v2.sv']);j.run('elaborate','xelab',['tb_pipeline_v2','-s','pipeline','-O0','-mt','off'])
 idx=json.loads((PKG/'golden_integer/index.json').read_text('utf-8'))['samples'];results=[]
 for i in range(worker,len(idx),2):
  item=idx[i];o=j.o/item['id'];o.mkdir();text=j.run(item['id'],'xsim',['pipeline','-runall','-testplusarg','CASE='+str(i),'-testplusarg','ROOT='+(H/'fixtures').as_posix(),'-testplusarg','OUT='+o.as_posix()]);assert 'PASS: V2_PIPELINE' in text
  gold=np.load(PKG/item['vectors'],allow_pickle=False);small=gold['locator_input_u8'];expected_raw=gold['locator_locator_fused_i32'].transpose(1,2,0).reshape(-1).astype('<i4')
  actual=np.array([int(x,16) for x in (o/'locator_output.mem').read_text().split()],dtype='<u4').view('<i4');assert np.array_equal(actual,expected_raw)
  camera={int(a,16):int(b,16) for a,b in (line.split() for line in (o/'camera_words.txt').read_text().splitlines())};assert sorted(camera)==list(range(4096));assert b''.join(camera[k].to_bytes(4,'little') for k in range(4096))==small.tobytes()
  meta={line.split()[0]:list(map(int,line.split()[1:])) for line in (o/'metadata.txt').read_text().splitlines()};bbox=meta['BBOX'];result=meta['RESULT'];e=item['pipeline'];cell=e['peak_xy'][1]*16+e['peak_xy'][0];q=gold['locator_locator_fused_i32'][:,cell//16,cell%16]
  assert bbox[:6]==[cell,*map(int,q)] and bool(result[0])==e['detected']
  if e['detected']:
   roi=e['roi_source'];side=roi[2]-roi[0];assert bbox[7:10]==[roi[0],roi[1],side] and meta['SMALL']==[e['small_roi']['sx'],e['small_roi']['sy'],e['small_roi']['ss']]
   crop=np.array([int(x,16) for x in (o/'classifier_input.mem').read_text().split()],dtype='u1');assert np.array_equal(crop,gold['classifier_input_u8'].reshape(-1))
   logits=np.array([int(x,16) for x in (o/'classifier_logits.mem').read_text().split()],dtype='<u4').view('<i4');assert np.array_equal(logits,gold['classifier_fc2_logits_i32'])
   cls=e['classifier']['class_id'];assert result[1]==cls and result[2]=={4:5,5:4}.get(cls,cls)
  else:assert result[2]==7 and not (o/'classifier_input.mem').read_text() and not (o/'classifier_logits.mem').read_text()
  results.append(dict(sample=item['id'],result='PASS_ALL_STAGES_EXACT',detected=e['detected'],model_class=None if not e['classifier'] else e['classifier']['class_id']))
 (j.o/'RESULTS.json').write_text(json.dumps(dict(result='PASS_REAL_DVP_TO_CLASSIFIER_B_PIPELINE',samples=results),indent=2)+'\n');return results

def main():
 global ATTEMPT
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='a1');ap.add_argument('stage',choices=['prepare','unit','classifier','locator','pipeline','final']);args=ap.parse_args();assert re.fullmatch('a[0-9]+',args.attempt);ATTEMPT=args.attempt
 if args.stage=='prepare':prepare();return
 if args.stage=='pipeline':
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(pipeline_worker,range(2)))
  assert sum(map(len,results))==26;print('PASS: ALL_26_REAL_PIPELINE_CASES',flush=True);return
 j=Job(args.stage)
 benches={'unit':['native_motion/sim/black_scene_v2/tb_gate_v2.sv','native_motion/sim/black_scene/tb_geometry_black.sv','native_motion/sim/black_scene/tb_geometry_ema.sv','native_motion/sim/black_scene/tb_gesture_time_filter.sv','native_motion/sim/black_scene/tb_camera_release.sv','native_motion/sim/black_scene/tb_a_safety.sv','native_motion/sim/phase2_alternative/tb_exposure_adapter.sv','native_motion/sim/phase2_alternative/tb_exposure_shared_sccb.sv'],
 'classifier':['native_motion/sim/black_scene/tb_classifier_real.sv'],'locator':['native_motion/sim/black_scene/tb_locator_context.sv'],'final':['native_motion/sim/black_scene_v2/tb_final_top_v2.sv']}[args.stage]
 j.compile(benches);tops=[Path(p).stem for p in benches]
 for top in tops:j.simulate(top,['-testplusarg','ROOT='+(H/'fixtures').as_posix()] if args.stage=='final' else ())
 (j.o/'RESULTS.json').write_text(json.dumps(dict(result='PASS_REAL_RTL_'+args.stage.upper(),tops=tops,samples=26 if args.stage in ('classifier','locator') else None,board_access=False),indent=2)+'\n');print('PASS: V2_'+args.stage.upper(),flush=True)
if __name__=='__main__':main()
