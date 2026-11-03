const $=s=>document.querySelector(s);
const names={red_cube:'红色方块',yellow_cube:'黄色方块',blue_cube:'蓝色方块',eraser:'橡皮',small_canister:'小圆罐'};
const shapes={red_cube:'cube',yellow_cube:'cube yellow',blue_cube:'cube blue',eraser:'eraser',small_canister:'canister'};
const states={OFF:'尚未启用',IDLE:'等待手势',WAIT_PATH:'AI PC 正在规划',PRECHECK:'FPGA 校验路径',RUN:'执行任务',WAIT_PALM:'等待掌心确认',STOPPING:'取消减速中',RETRACE:'沿路径返回',HALT:'保持当前姿态',FAULT:'故障停止'};
let rendered='',mode='A',chosen=['red_cube','yellow_cube','blue_cube'],state=null,token='',pending=null,busy=false;
const message=(text,error=false)=>{const e=$('#message');e.textContent=text;e.classList.toggle('error',error);};
function render(){
 $('#mode-a').classList.toggle('selected',mode==='A');$('#mode-b').classList.toggle('selected',mode==='B');
 $('#selection-hint').textContent=mode==='A'?'A 模式沿用已测试的三色槽位。数字 1 / 2 / 3 对应红 / 黄 / 蓝。':'依次点击物品，按选择顺序绑定数字 1 / 2 / 3；再次点击可移除。B 抓取交付采用 Giao 分段速度与原生轨迹；当前开放三类。';
 const signature=mode+'|'+chosen.join(',');
 if(signature!==rendered){rendered=signature;
 $('#objects').replaceChildren();
 for(const id of mode==='A'?['red_cube','yellow_cube','blue_cube']:['red_cube','eraser','small_canister']){
  const card=document.createElement('button');card.className='object'+(chosen.includes(id)?' chosen':'');
  const shape=document.createElement('div');shape.className='shape '+shapes[id];card.append(shape);
  const name=document.createElement('span');name.textContent=names[id];card.append(name);
  const sub=document.createElement('small');sub.textContent=id==='eraser'?'65 × 15 × 15 mm':id==='small_canister'?'Ø25 × 46 mm':'30 × 30 × 30 mm';card.append(sub);
  if(chosen.includes(id)){const n=document.createElement('b');n.className='number';n.textContent=chosen.indexOf(id)+1;card.append(n);}
  card.onclick=()=>{if(mode==='A'){message('A 模式为固定红 / 黄 / 蓝映射。');return;}if(busy||pending){message('配置正在处理，收到确认后才可修改物品。',true);return;}chosen=chosen.includes(id)?chosen.filter(x=>x!==id):[...chosen,id];render();};$('#objects').append(card);
 }
 $('#bindings').textContent=chosen.length?chosen.map((x,i)=>`${i+1} → ${names[x]}`).join('　 /　 '):'至少选择一个物品';
 }
 $('#lock').disabled=!state?.control.idle||!chosen.length||busy||!!pending;
 $('#lock-reason').textContent=pending||busy?'正在确认配置：'+(state?.control.mode_progress||'等待 FPGA 回报')+'。':!state?.control.idle?(state?.control.lock_block_reasons||['等待 FPGA 的真实状态']).join('；')+'。':!chosen.length?'请至少选择一个物品。':'可以锁定配置；A/B 切换包含固定 HOME 过渡。RGB 画面不影响配置锁定，实际抓取时检查所选物品。';
}
for(const m of ['A','B'])$('#mode-'+m.toLowerCase()).onclick=()=>{if(busy||pending){message('配置正在处理，请等待当前切换完成。',true);return;}mode=m;chosen=m==='A'?['red_cube','yellow_cube','blue_cube']:['red_cube','eraser','small_canister'];render();};
async function action(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify(body)});const result=await r.json();if(!r.ok){const error=new Error(result.error||'请求失败');error.outcome=result.outcome;throw error;}return result;}
$('#lock').onclick=async()=>{
 if(busy||pending||!state?.control.idle){message($('#lock-reason').textContent,true);return;}busy=true;pending=crypto.randomUUID();render();message('配置已发送；如需切换，将先执行固定 HOME 过渡，请保持工作区清空。');
 try{await action('/api/mode-lock',{contract:'zhixing.console.bridge.v1',request_id:pending,expected_revision:state.control.revision,mode,gesture_bindings:chosen.map((x,i)=>({gesture:i+1,object_id:x}))});}
 catch(e){if(e.outcome==='unknown')message('设备正在处理，请等待真实状态回报；不会重复发送切换动作。');else{message(e.message,true);pending=null;}}
 finally{busy=false;render();}
};
async function devices(){try{const r=await fetch('/api/devices');const rows=await r.json();if(!r.ok)throw new Error(rows.error);const s=$('#camera-list');s.replaceChildren(new Option('选择已标定的普通 RGB 摄像头',''));for(const d of rows)s.add(new Option(d.FriendlyName+' · '+d.Index,d.DevicePath));}catch(e){message(e.message,true);}}
$('#refresh-camera').onclick=devices;
$('#connect-camera').onclick=async()=>{try{const path=$('#camera-list').value;if(!path)throw new Error('请先选择已标定的 RGB 摄像头');$('#connect-camera').disabled=true;await action('/api/camera',{device_path:path});message('相机已打开，正在加载模型并验证实际 ROCm 推理。');}catch(e){message(e.message,true);$('#connect-camera').disabled=false;}};
for(const ok of [true,false])$(ok?'#success':'#failure').onclick=async()=>{try{await action('/api/observation',{physical_success:ok,note:$('#observation-note').value});$('#observation-result').textContent='实物观察已写入本次会话日志';}catch(e){message(e.message,true);}};
async function poll(){
 try{
  const r=await fetch('/api/status');if(!r.ok)throw new Error('状态读取失败');state=await r.json();const c=state.control,d=c.device||{};
  $('#dot').style.background=c.connected?'#39875b':'#aaa';$('#connection').textContent=c.connected?'FPGA 已连接 · 实时反馈':'等待 FPGA 连接';
  const switching=!!c.inflight_request_id||c.last_request_outcome==='unknown'||(pending&&c.last_request_id!==pending);
  $('#revision').textContent=c.active_mode?`已锁定 · 修订 ${c.revision}`:'尚未锁定';$('#active-mode').textContent=c.active_mode?`MODE ${c.active_mode}`:'未锁定';
  $('#state').textContent=c.transition_fault?'切换或任务异常':switching?'模式切换中':states[d.state]||'未连接';
  $('#task-detail').textContent=c.task?`${names[c.task.class_name]} · ${c.task.kind==='RESTOCK'?'公共点补回原位':'抓取并交付到手'} · 任务 ${c.task.task_id}`:c.connected?'任务只由数字手势启动；PALM 确认后交付，FIST 普通取消。':'状态来自 FPGA 寄存器。连接前不会展示模拟进度。';
  for(const [id,key] of [['#done','done_counter'],['#restock','restocked_tasks'],['#cancelled','cancelled_counter']])$(id).textContent=c.connected?d[key]??'—':'—';
  $('#home').textContent=c.connected?(d.at_home?'当前 HOME':d.session_phase==='SWITCHING_HOME'?'HOME 过渡中':'任务路径中'):'—';$('#holding').textContent=c.connected?(d.holding?'已夹取（程序状态）':'空闲'):'—';
  $('#feedback').textContent=c.connected?`${d.feedback_age_at_snapshot_ms} ms`:'—';$('#fault').textContent=c.connected?[d.fault,d.fault_detail].filter(Boolean).join(' · '):'—';
  $('#source-status').textContent=c.shared_red?.a_gesture_disabled?'共享红块目前位于 A 红槽以外，A 的数字 1 暂停响应。请将红块复位到 A 红槽，或放到公共点后重新锁定 A 配置，再做数字 1 补回。':c.empty_sources.length?'原位已标空：'+c.empty_sources.map(x=>names[x]).join('、')+'。请将物品放到公共点 (300, 200) mm，并清空原位，再做对应数字手势补回。A/B 共用红块，库存同步。':'A/B 共用同一红块，库存同步；B 其他物品按原位补回，调整手势顺序不改变原位。';
  if(pending&&c.last_request_id===pending){if(c.last_request_outcome==='applied'){message(`配置已生效：模式 ${c.active_mode}。请先撤去手势，再用数字选择物品。`);pending=null;}else if(c.last_request_outcome==='rejected'){message('配置未应用：'+(c.last_request_error||'请查看设备锁定条件。'),true);pending=null;}}
  if(c.transition_fault)message(c.transition_fault,true);
  $('#planning-error').textContent=state.planning_error?'任务路径未提交：'+state.planning_error:'';
  const p=state.planning;$('#planning-progress').textContent=p?`${p.background&&!c.task?'后台准备':'当前规划'} · ${names[p.class_name]||p.class_name} · ${p.stage} · ${p.elapsed_s} 秒`:'';
  const cam=state.camera,obs=cam.observation;$('#gpu-status').textContent=cam.ready?`ROCm · ${Math.round(obs.total_ms)} ms / 帧`:cam.error?'视觉未就绪':'ROCm GPU · 等待推理';
  if(obs){$('#preview').hidden=false;$('#camera-empty').style.display='none';$('#preview').src='/camera.jpg?t='+obs.frame_id;}
  $('#camera-reason').textContent=cam.error?'相机或推理错误：'+cam.error+'；请结束会话、排除原因后重启。':cam.ready?'普通 RGB 已就绪。每次任务只校验选中的物品。':'RGB 尚未就绪或图像超过 1 秒；可锁定 B 配置，抓取需等待新鲜画面。';
  $('#vision-results').replaceChildren();
  for(const row of state.vision_diagnostics||[]){const line=document.createElement('p');const mapping=c.gesture_bindings.find(x=>x.object_id===row.class_name);line.textContent=`${mapping?'数字 '+mapping.gesture+' → ':''}${names[row.class_name]}：${row.reason}`+(row.centre_mm?`；坐标 ${row.centre_mm.map(n=>n.toFixed(1)).join(', ')} mm`:'')+(row.profile_id?`；配置 ${row.profile_id}`:'')+(Object.keys(row.measurements||{}).length?`；测量 ${JSON.stringify(row.measurements)}`:'');line.className=row.task_vision_ready?'vision-pass':'vision-blocked';$('#vision-results').append(line);}
  const b=state.boundaries;if(b)$('#workspace-bounds').textContent=`源位中心：X ${b.workspace_xy_mm[0]}～${b.workspace_xy_mm[1]}、Y ${b.workspace_xy_mm[2]}～${b.workspace_xy_mm[3]} mm。三类取消25/150 mm锚点半径限制；红块统一采用下探12 mm配置。物品按桌面轴摆正，允许轻微倾斜；反解与轨迹几何仍逐次检查。${b.note}`;
  render();
 }catch(e){state=null;$('#connection').textContent='服务连接中断';$('#dot').style.background='#aaa';render();$('#lock-reason').textContent='无法读取本地服务状态：'+e.message+'。请检查启动终端及本次 runs 日志。';}
 setTimeout(poll,400);
}
try{token=(await (await fetch('/api/session')).json()).token;render();poll();}catch(e){message('本地服务未连接，请通过启动脚本打开本页面。',true);}
