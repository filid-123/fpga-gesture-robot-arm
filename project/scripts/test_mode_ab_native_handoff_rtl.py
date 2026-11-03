"""Real root B native -> ownership fence -> host P2P -> B native regression."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,re,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from test_mode_ab_route_aperture_rtl import TB
from run_mode_a_v3_checks import source_list,PKG
from pc.mode_ab.native_backend import backend_writes
from run_mode_a_restock import math_ceil_velocity,math_ceil_acceleration

def main(out):
 out.mkdir(parents=True,exist_ok=False);text=TB
 text=text.replace('reg[7:0]aa=0,ra=0;','reg[11:0]aa=0,ra=0;reg[1:0]bus=0;')
 text=text.replace('wire awr,wr,bv,arr,rv;wire[31:0]rd;wire[1:0]bp,rp;',
  'wire awr,wr,bv,arr,rv;wire[31:0]rd;wire[1:0]bp,rp;wire[2:0]awrs,wrs,bvs,arrs,rvs;wire[95:0]rds;wire[5:0]bps,rps;assign awr=awrs[bus];assign wr=wrs[bus];assign bv=bvs[bus];assign arr=arrs[bus];assign rv=rvs[bus];assign rd=rds[bus*32+:32];assign bp=bps[bus*2+:2];assign rp=rps[bus*2+:2];')
 for a,b in [('(aa)','(aa[7:0])'),('(ra)','(ra[7:0])'),('(av)','(av&&bus==0)'),('(wv)','(wv&&bus==0)'),('(arv)','(arv&&bus==0)'),('(awr)','(awrs[0])'),('(wr)','(wrs[0])'),('(bv)','(bvs[0])'),('(arr)','(arrs[0])'),('(rv)','(rvs[0])'),('(rd)','(rds[31:0])'),('(bp)','(bps[1:0])'),('(rp)','(rps[1:0])')]:
  # Only the instance port list contains these parenthesized shorthand names.
  text=text.replace(a,b)
 for i,name in ((1,'arm'),(2,'plan')):
  a=text.index('.s_axi_'+name+'_awvalid');b=text.index('\n',a)
  connections=[]
  vals=dict(awaddr='aa',awprot="3'd0",awvalid=f'av&&bus=={i}',awready=f'awrs[{i}]',wdata='wd',wstrb="4'hf",wvalid=f'wv&&bus=={i}',wready=f'wrs[{i}]',bresp=f'bps[{i*2}+:2]',bvalid=f'bvs[{i}]',bready="1'b1",araddr='ra',arprot="3'd0",arvalid=f'arv&&bus=={i}',arready=f'arrs[{i}]',rdata=f'rds[{i*32}+:32]',rresp=f'rps[{i*2}+:2]',rvalid=f'rvs[{i}]',rready="1'b1")
  text=text[:a]+','.join('.s_axi_'+name+'_'+key+'('+value+')' for key,value in vals.items())+','+text[b:]
 text=text.replace(".motion_enable_in(1'b0)",".motion_enable_in(1'b1)")
 text=text.replace('task write(input[7:0]a','task write(input[11:0]a').replace('task read(input[7:0]a','task read(input[11:0]a')
 a=text.index('initial begin\n repeat(8)');text=text[:a]+r'''
reg cv=0;reg[2:0]cc=0;reg[191:0]target=0;
reg[31:0]setup[0:4095];integer n=0,limit=0;
task native_cmd(input[2:0]c);
begin @(negedge clk);cc=c;cv=1;while(!dut.u_task.native_ready)@(negedge clk);@(negedge clk);cv=0;
while(!dut.u_task.native_done)@(negedge clk);if(!dut.u_task.native_ok)$fatal(1,"Native ownership command rejected %d",c);@(negedge clk);end endtask
initial begin
 $readmemh("setup.mem",setup);repeat(8)@(negedge clk);rst=1;repeat(8)@(negedge clk);
 force dut.u_task.native_valid=cv;force dut.u_task.native_code=cc;force dut.u_task.op_target=target;
 force dut.u_task.op_na=16'd0;force dut.u_task.op_n=16'd16;force dut.u_task.op_profile=1'b0;
 bus=1;for(integer i=0;i<setup[0];i=i+1)write(setup[1+2*i],setup[2+2*i]);
 write(12'h020,16);write(12'h038,91<<8);write(0,1);limit=0;
 while(!dut.u_task.u_motion.u_actuator.u_arm_backend.config_valid)begin @(negedge clk);limit=limit+1;if(limit>10000)$fatal(1,"Backend commit failed");end
 write(4,1);repeat(8)@(negedge clk);
 bus=0;write(0,1);write(28,16);
 for(integer plane=0;plane<6;plane=plane+1)begin write(16,plane);write(20,0);write(128,0);end
 write(16,7);write(20,0);
 for(integer i=0;i<6;i=i+1)begin target[i*32+:32]=setup[4000+i];write(128+4*i,setup[4000+i]);end
 write(16,6);
 for(integer i=0;i<192;i=i+1)begin write(20,i);case(i%4)0:write(128,65536);1:write(128,512);default:write(128,(254<<16)|2640);endcase end
 write(0,2);native_cmd(7);wait(dut.u_task.native_pl_status[2:0]==4);
 if(dut.u_task.native_last!==target)$fatal(1,"Native B did not reach endpoint");
 native_cmd(6);repeat(3)@(negedge clk);
 if(dut.u_task.u_motion.route_selected!==0)$fatal(1,"B ownership fence failed to restore host P2P source");
 bus=2;write(12'h040,16);write(12'h044,4);write(12'h048,1);write(12'h04c,512);write(12'h050,50000000);
 for(integer i=0;i<6;i=i+1)begin
  write(12'h100+i*32,target[i*32+:32]);write(12'h104+i*32,target[i*32+:32]+(i==0?656:0));
  write(12'h108+i*32,VMAX);write(12'h10c+i*32,AMAX);
 end
 target[31:0]=target[31:0]+656;write(0,1);limit=0;
 while(dut.u_task.native_pl_status[2:0]!=4||dut.u_task.native_last!==target)begin @(negedge clk);limit=limit+1;if(limit>1000000)$fatal(1,"Host HOME transition stuck error=%h status=%h last=%h target=%h sel=%d core=%d armerr=%h armstate=%h owner=%d",dut.u_task.native_pl_error,dut.u_task.native_pl_status,dut.u_task.native_last,target,dut.u_task.u_motion.route_selected,dut.u_task.u_motion.u_planner.core_state,dut.u_task.u_motion.u_actuator.u_arm_backend.error_status,dut.u_task.u_motion.u_actuator.u_arm_backend.u_core.state,dut.u_task.owner_s4);end
 $display("PASS: full root native B completes, ownership fence acknowledges and restores host P2P HOME transition");
 native_cmd(6);native_cmd(7);wait(dut.u_task.native_pl_status[2:0]==4);
 if(dut.u_task.native_last[31:0]!==32'd0)$fatal(1,"Native B could not resume after host P2P");
 $display("PASS: host P2P returns ownership to native B with the same immutable program");
 // Audit REQP-1839 at the real asynchronously reset elastic-buffer boundary.
 force dut.u_task.u_motion.u_actuator.u_mux.m_ready=1'b0;
 native_cmd(7);wait(dut.u_task.u_motion.u_actuator.u_mux.buf_valid);
 #2;rst=0;#1;
 if(dut.u_task.u_motion.u_actuator.u_mux.buf_valid!==0)$fatal(1,"Async buffer reset did not close the output");
 repeat(3)@(negedge clk);
 if(dut.u_task.u_motion.g_b_program.u_player.committed!==0||dut.u_task.u_motion.g_b_program.u_player.base_mask!==0||dut.u_task.u_motion.g_b_program.u_player.desc_mask!==0)$fatal(1,"Reset retained a trusted RAM image");
 if(dut.u_task.u_motion.u_actuator.u_arm_backend.config_valid!==0)$fatal(1,"Reset retained backend configuration");
 rst=1;release dut.u_task.u_motion.u_actuator.u_mux.m_ready;repeat(6)@(negedge clk);
 bus=0;read(4,2);
 @(negedge clk);cc=7;cv=1;@(negedge clk);cv=0;
 while(!dut.u_task.native_done)@(negedge clk);
 if(dut.u_task.native_ok!==0)$fatal(1,"Motion accepted before complete program reload");
 $display("PASS: asynchronous reset drains the real elastic output, invalidates route/backend configuration and rejects motion before complete RAM reload");$finish;
end
initial begin #10000000;$fatal(1,"Native/host ownership handoff timeout");end
endmodule
'''
 text=text.replace('VMAX',str(math_ceil_velocity())).replace('AMAX',str(math_ceil_acceleration()))
 plan=json.loads((ROOT/'candidate/bank1/PLAN_NATIVE.json').read_bytes());writes=backend_writes(plan)
 words=[len(writes),*[v for a,b in writes for v in (a-0x43c30000,b)]];words+=[0]*(4000-len(words));words += [0,0,65536,0,0,round(2.7*65536)]
 (out/'setup.mem').write_text(''.join(f'{int(x)&0xffffffff:08x}\n' for x in words))
 for key,path in [('LOCFILE',PKG/'quantized/locator/model_rom_16k.mem'),('WFILE',PKG/'quantized/classifier/weights_all.mem'),('DFILE',PKG/'quantized/classifier/layer_descriptors.mem'),('CAMFILE',ROOT/'native_motion/rtl/autonomous/ov5640_vga_yuyv.mem')]:text=text.replace(key,path.as_posix())
 p=out/'native_motion/geometry_alpha_q16.mem';p.parent.mkdir();shutil.copyfile(ROOT/'native_motion/geometry_alpha_q16.mem',p);shutil.copyfile(p,out/'geometry_alpha_q16.mem')
 bench=out/'tb.sv';bench.write_text(text);files=source_list()+[bench];(out/'sources.f').write_text('\n'.join(f.as_posix() for f in files));records=[]
 for label,tool,args in [('compile','xvlog',['-sv','-i',ROOT/'native_motion/rtl/autonomous','-f',out/'sources.f']),('elaborate','xelab',['tb','-s','handoff','-O0','-mt','off']),('run','xsim',['handoff','-runall'])]:
  p=subprocess.run(['cmd.exe','/d','/c','E:/Xilinx/2026.1/Vivado/bin/'+tool+'.bat',*map(str,args)],cwd=out,capture_output=True,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
  text=(p.stdout+p.stderr).decode('utf-8',errors='replace');(out/(label+'.txt')).write_text(text);print(label,p.returncode,flush=True);records.append(dict(stage=label,exit_code=p.returncode))
  if p.returncode or re.search('(ERROR:|Fatal:|FATAL:|FAIL:|cannot open|failed to open)',text,re.I):raise RuntimeError(text[-5000:])
 (out/'result.json').write_text(json.dumps(dict(passed=True,checks=[s for s in text.splitlines() if s.startswith('PASS:')],hardware_access=False,
  commands=records,source_hashes={f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}),indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);main(p.parse_args().out.resolve())
