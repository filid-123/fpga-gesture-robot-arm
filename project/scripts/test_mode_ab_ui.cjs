// Exercise the actual production UI against explicit synthetic states, no devices.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path'),root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'web/mode-ab/index.html'),'utf8');
const elements=new Map();
class Element{
 constructor(){this.textContent='';this.children=[];this.style={};this.disabled=false;this.hidden=false;this.value='';this.classList={toggle(){}};}
 append(x){this.children.push(x)}replaceChildren(...xs){this.children=xs}add(x){this.children.push(x)}
}
for(const match of html.matchAll(/id="([^"]+)"/g))elements.set('#'+match[1],new Element());
const get=s=>{assert(elements.has(s),'HTML is missing '+s);return elements.get(s)};
let current={control:{connected:false,idle:false,device:{},empty_sources:[],gesture_bindings:[],lock_block_reasons:['等待新鲜 FPGA 状态及正确 ABI']},camera:{ready:false,error:null},vision_diagnostics:[]};
let fail=false,lastBody=null;
const context=vm.createContext({document:{querySelector:get,createElement:()=>new Element()},Option:Element,
 crypto:{randomUUID:()=> '00000000-0000-4000-8000-000000000001'},setTimeout(){},
 fetch:async (url,args)=>{if(fail)throw Error('模拟连接失败');if(args){lastBody=JSON.parse(args.body);return {ok:true,json:async()=>({applied:true})}}return {ok:true,json:async()=>structuredClone(current)}}});
let source=fs.readFileSync(path.join(root,'web/mode-ab/app.js'),'utf8');source=source.slice(0,source.lastIndexOf("try{token=(await"));
(async()=>{
 const ui=await vm.runInContext('(async()=>{'+source+';return {poll,render};})()',context);
 let checks=0;const check=(v,m)=>{assert(v,m);checks++};
 ui.render();check(get('#lock').disabled,'Disconnected cannot lock');
 current.control={...current.control,connected:true,idle:true,revision:0,device:{state:'IDLE',at_home:true,holding:false,fault:'NONE'},lock_block_reasons:[]};
 await ui.poll();get('#mode-b').onclick();check(!get('#lock').disabled,'B config must not depend on RGB opening');
 current.camera.ready=true;current.camera.observation={frame_id:1,total_ms:500};current.vision_diagnostics=[{class_name:'eraser',reason:'未检测到橡皮',task_vision_ready:false}];
 await ui.poll();check(!get('#lock').disabled,'No visible object must not block config');
 check(get('#vision-results').children[0].textContent.includes('未检测到橡皮'),'Every class exposes its failure reason');
 current.control.idle=false;current.control.lock_block_reasons=['夹爪仍持物','尚未回到当前模式 HOME'];await ui.poll();
 check(get('#lock').disabled&&get('#lock-reason').textContent.includes('夹爪仍持物'),'Lock denial explains actual conditions');
 current.control.idle=true;await ui.poll();await get('#lock').onclick();
 check(lastBody.mode==='B'&&lastBody.gesture_bindings.length===3,'Mode lock submits selected mapping');
 current.control.last_request_id=lastBody.request_id;current.control.last_request_outcome='applied';current.control.active_mode='B';current.control.revision=1;
 current.planning_error='SOURCE_CHANGED：位移 4 mm，允许 3 mm';await ui.poll();
 check(get('#message').textContent.includes('配置已生效')&&get('#planning-error').textContent.includes('允许 3 mm'),'Task errors remain separate from mode acknowledgement');
 current.planning={class_name:'red_cube',stage:'检查源位轨迹',elapsed_s:1.2};await ui.poll();
 check(get('#planning-progress').textContent.includes('1.2 秒'),'Planning phase/elapsed visible');
 current.camera.error='DirectShow camera open failed';await ui.poll();check(get('#camera-reason').textContent.includes('DirectShow'),'Camera errors visible');
 fail=true;await ui.poll();check(get('#lock').disabled&&get('#lock-reason').textContent.includes('模拟连接失败'),'Network failure clears stale lock permission');
 process.stdout.write(JSON.stringify({passed:true,checks,hardware_access:false,physical_test:'NOT_RUN'})+'\n');
})().catch(e=>{console.error(e);process.exitCode=1});
