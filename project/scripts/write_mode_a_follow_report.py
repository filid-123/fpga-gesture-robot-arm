"""Local-only figures and final four-region trajectory report."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(root):
 plans=[json.loads((root/f'bank{i}/PLAN_NATIVE.json').read_text('utf-8')) for i in range(3)]
 t=json.loads((root/'S4_BANKED_CANDIDATE.json').read_text('utf-8'));out=root/'figures';out.mkdir(exist_ok=True)
 colors=['#3276b8','#289b67','#b24b8c']
 fig,(ax,zoom)=plt.subplots(1,2,figsize=(13,5.5),layout='constrained')
 for bank,(p,c) in enumerate(zip(plans,colors)):
  v=json.loads((root/f'bank{bank}/PATH_PREVIEW.json').read_text('utf-8'))
  for r in v['paths']:
   pts=[x['D_mm'] for x in r['rows']];ax.plot([p[0] for p in pts],[p[1] for p in pts],color=c,alpha=.55,lw=1,label=f'bank{bank}' if r['object']==1 else None)
  pre,h,clear=[p['layout']['common_D_mm'][k] for k in ('PRE','H','H_CLEAR')]
  zoom.plot([pre[1],h[1],clear[1]],[pre[2],h[2],clear[2]],'-o',color=c,label=f'bank{bank}')
  zoom.text(pre[1],pre[2]+2,f'PRE{bank}');zoom.text(h[1],h[2]-3,f'H{bank}')
 ax.add_patch(plt.Rectangle((0,0),390,390,fill=False,ls='--',ec='#777',label='Nominal tabletop FOV'))
 for p,c in zip(plans[1]['layout']['slots_D_mm'],['red','#c59c00','blue']):ax.add_patch(plt.Rectangle((p[0]-15,p[1]-15),30,30,fc=c,alpha=.75))
 ax.scatter(585,25,c='black');ax.text(598,25,'Base');ax.scatter(195,195,c='black',marker='x');ax.text(180,210,'OV5640 z333',ha='right')
 ax.set(xlim=(-15,700),ylim=(-15,410),xlabel='Desk X mm',ylabel='Desk Y mm',title='Three visible positions / full three-color routes');ax.set_aspect('equal');ax.legend(loc='lower left',fontsize=8);ax.grid(alpha=.2)
 zoom.set(xlim=(120,295),ylim=(165,202),xlabel='Desk Y mm',ylabel='TCP Z mm',title='120mm follow span / heights retained');zoom.legend();zoom.grid(alpha=.2)
 for ext in ('png','svg','pdf'):fig.savefig(out/('mode_a_follow_paths.'+ext),dpi=180)
 plt.close(fig)
 fig,ax=plt.subplots(figsize=(7,4.5),layout='constrained');bounds=[16,54,74,112]
 for i in range(3):
  bank=2-i;lo,hi=bounds[i:i+2];ax.add_patch(plt.Rectangle((0,lo),128,hi-lo,fc=colors[bank],alpha=.2));ax.text(64,(lo+hi)/2,f'Band{i+1} -> bank{bank}, H Y={plans[bank]["layout"]["common_D_mm"]["H"][1]}mm',ha='center',va='center')
 for y in bounds:ax.axhline(y,color='#777',ls='--',lw=.7)
 ax.set(xlim=(0,128),ylim=(128,0),xlabel='Raw Locator center X',ylabel='Raw Locator center Y',title='Independent position / thresholds54,74 / image up -> desk+Y')
 for ext in ('png','svg','pdf'):fig.savefig(out/('mode_a_follow_regions.'+ext),dpi=180)
 plt.close(fig)
 lines=['# 最新路径规划 v0.11.0：独立Locator三档跟手','','采用原桌面坐标，H/PRE前后总跨度120mm，分界收进有效识别范围54/74。定位有效且新鲜时，原始框中心独立80ms/2帧去抖；PALM/FIST保留原语义确认。无需实体采样。','','![轨迹](figures/mode_a_follow_paths.png)','','![区域](figures/mode_a_follow_regions.png)','','|bank|图像Y|PRE mm|H mm|红/黄/蓝插补秒|','|---|---|---|---|---|']
 for i,p in enumerate(plans):
  c=p['layout']['common_D_mm'];bounds_text=['74～111','54～73','16～53'][i];lines.append(f'|{i}|{bounds_text}|{c["PRE"]}|{c["H"]}|'+ '/'.join(f'{r["seconds"]:.2f}' for r in p['paths'])+'|')
 lines+=['','相机(195,195,333)、三块原中心红(530,250,15)/黄(650,250,15)/蓝(590,320,15)、底座(585,25)、B(360,200,160)保持。H X285/Z175，PRE X350/Z180，H_CLEAR Z195；最上区H35°至退爪40°，其余40°。坐标与区域为有限跟随方案，非真实三维相机标定。','','每bank47关键点/59共享段/最大栈23；bank3与bank2同值备用、不启用。表内插补时间不含启动接HOME、固定停稳、PRE至少2秒/PALM0.5秒和人工等待。各bank/SUMMARY.json给出分解。','','|起点bank→终点bank|0|1|2|','|---|---|---|---|']
 for a in range(3):lines.append('|'+str(a)+'|'+'|'.join(f'{t["align_pairs"][4*a+b]["seconds"]:.2f}s' for b in range(3))+'|')
 lines+=['','上述是完整端点间对齐时长；途中有新稳定区域则PAUSE→等待pending清空→CLEAR→从LAST_DELIVERED按实际角差重定时，不等待旧段结束、不跳回起点。局部停稳48ms。新N/Na对应1/2/4/8/12/20/30/45/90°上界，N12/16/20/28/32/44/64/92/184；Na=N/4。没有在线IK，运行时只从有限PRE目标选择并执行关节空间插补。','','整体规划速度上限约增10%，T102660/33，20ms/50Hz，每3运动帧查询反馈。实际端到端速度/制动与跟随延迟未测，不将软件暂停视作实体瞬间制动。','','HOME开爪→原槽上方→下降→夹紧→同XY抬升→B→中PRE→三档跟随→PALM锁定→8段递送→开爪→2段退爪→HOME。FIST1秒释放提交前归还原槽/开爪/HOME，恢复库存；位置精度继续observe_all。','','各bank/JOINT_TARGETS_NATIVE.csv是六轴原生弧度/点位/时长，PLAN_NATIVE含精确S2采样；cancel_replay来自实际FSM13条发出目标的回放，9条正常任务及4种归还/改向情景。Coppelia停止运动学和几何附着包含真实网格/桌面/相机/物块/掌面代理，未模拟舵机控制和接触动力学。本版实体NOT_RUN。']
 (root/'PATH_PLAN_CN.md').write_text('\n'.join(lines)+'\n','utf-8')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);main(ap.parse_args().candidate)
