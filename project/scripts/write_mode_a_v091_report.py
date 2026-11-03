"""Standalone final-bank path report and geometric figures; no hardware."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(root):
 plans=[json.loads((root/f'bank{i}/PLAN_NATIVE.json').read_text('utf-8')) for i in range(3)]
 out=root/'figures';out.mkdir(exist_ok=True)
 fig,(ax,zoom)=plt.subplots(1,2,figsize=(13,5.5),gridspec_kw={'width_ratios':[1.25,1]},layout='constrained')
 for bank,(p,c) in enumerate(zip(plans,['#3276b8','#289b67','#b24b8c'])):
  preview=json.loads((root/f'bank{bank}/PATH_PREVIEW.json').read_text('utf-8'))
  for r in preview['paths']:
   pts=[x['D_mm'] for x in r['rows']]
   ax.plot([v[0] for v in pts],[v[1] for v in pts],color=c,alpha=.65,lw=1,label=f'bank{bank}' if r['object']==1 else None)
  pts=p['layout']['common_D_mm'];pre,h,clear=[pts[k] for k in ('PRE','H','H_CLEAR')]
  zoom.plot([pre[1],h[1],clear[1]],[pre[2],h[2],clear[2]],'-o',color=c,label=f'bank{bank}: Hy={h[1]}')
  zoom.text(pre[1],pre[2]+1.5,f'PRE{bank}',fontsize=9,color=c)
  zoom.text(h[1],h[2]-4,f'H{bank}',fontsize=9,color=c)
 ax.add_patch(plt.Rectangle((0,0),310,310,fill=False,ls='--',ec='#777777',label='Camera view'))
 layout=plans[1]['layout']
 for pt,c,label in zip(layout['slots_D_mm'],['#db3c30','#c59c00','#226fb2'],['Red','Yellow','Blue']):
  ax.add_patch(plt.Rectangle((pt[0]-15,pt[1]-15),30,30,fc=c,alpha=.85));ax.text(pt[0],pt[1]+22,label,ha='center',fontsize=9)
 base=layout['base_axis_D_xy_mm'];ax.scatter(*base,s=150,marker='o',color='#333333');ax.text(base[0]+12,base[1]+8,'Base')
 ax.scatter(195,195,s=100,marker='x',color='black');ax.text(180,210,'OV5640 z333',ha='right')
 ax.set(xlim=(-15,700),ylim=(-15,370),xlabel='Desk X (mm)',ylabel='Desk Y (mm)',title='Three banks / all object routes')
 ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(loc='upper left',fontsize=8)
 zoom.set(xlim=(120,210),ylim=(155,205),xlabel='Desk Y (mm)',ylabel='TCP Z (mm)',title='Local alignment and blind-delivery targets')
 zoom.grid(alpha=.2);zoom.legend(loc='lower right',fontsize=8)
 for ext in ('png','svg','pdf'):fig.savefig(out/('mode_a_v091_paths.'+ext),dpi=180)
 plt.close(fig)
 lines=['# 第二版最终路径规划 v0.9.1','','沿用第一稿实测坐标及残差反解，三组独立关键点共用段结构。物块和相机位置保持。画面上/中/下沿图像Y分区，映射为桌面前/中/后Y±20mm，高度保持；图像朝向需要以掌位采样确定，不从此几何图推断像素。','','![路径总图](figures/mode_a_v091_paths.png)','','| bank | PRE mm | H mm | 关键点/段/栈 | 红/黄/蓝插补秒 |','|---|---|---|---|---|']
 for i,p in enumerate(plans):
  points=p['layout']['common_D_mm'];lines.append(f"| {i} | {points['PRE']} | {points['H']} | 47/59/23 | "+'/'.join(f"{r["seconds"]:.2f}" for r in p['paths'])+' |')
 lines+=['','每色另加固定停留6.176秒、启动接HOME，以及PRE至少2秒/PALM0.5秒和人的等待时间；局部对齐每次插补0.88秒+固定352ms，重新开始PRE等待。速度上限和50Hz保持第一稿，三组同编号段使用三者最大N。HANDOVER沿PRE→H细分8段，工具倾角保持40°。','','完整每轴关节角、桌面坐标和段时长见各bank的JOINT_TARGETS_NATIVE.csv；PLAN_NATIVE.json含全部精确Q16采样，S4_BANKED_CANDIDATE.json为实际下载表。','', '顺序：HOME开爪→选定槽上方→下降→夹紧→同XY抬升→B→中央PRE→按图像离散区域移到侧PRE→PALM锁定→该侧H→开爪→H_CLEAR→HOME。取消先反向退回所选侧PRE，连接中央PRE，再按原抓取路径归还。','', '残差取自已通过A参考点，不构成额外实物标定。Coppelia为停止运动学，碰撞检查包含机械臂网格、桌面、相机、另两物块和掌面代理；不包含接触动力学或实机制动。新版本实体结果NOT_RUN。']
 (root/'PATH_PLAN_CN.md').write_text('\n'.join(lines)+'\n','utf-8')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);main(ap.parse_args().candidate)
