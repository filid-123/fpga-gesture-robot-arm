"""Local-only figures and final four-region trajectory report."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(root):
    plans=[json.loads((root/f'bank{i}/PLAN_NATIVE.json').read_text('utf-8')) for i in range(4)]
    t=json.loads((root/'S4_BANKED_CANDIDATE.json').read_text('utf-8'))
    out=root/'figures';out.mkdir(exist_ok=True)
    colors=['#3276b8','#289b67','#bb8524','#b24b8c']
    fig,(ax,zoom)=plt.subplots(1,2,figsize=(13,5.8),layout='constrained')
    for bank,(p,c) in enumerate(zip(plans,colors)):
        preview=json.loads((root/f'bank{bank}/PATH_PREVIEW.json').read_text('utf-8'))
        for r in preview['paths']:
            pts=[x['D_mm'] for x in r['rows']]
            ax.plot([v[0] for v in pts],[v[1] for v in pts],color=c,alpha=.5,lw=1,label=f'bank{bank}' if r['object']==1 else None)
        pts=p['layout']['common_D_mm'];pre,h,clear=[pts[k] for k in ('PRE','H','H_CLEAR')]
        zoom.plot([pre[1],h[1],clear[1]],[pre[2],h[2],clear[2]],'-o',color=c,label=f'bank{bank}: Hy={h[1]}')
        zoom.text(pre[1]+1,pre[2]+1.5,f'PRE{bank}',fontsize=9,color=c)
        zoom.text(h[1],h[2]-4,f'H{bank}',fontsize=9,color=c)
    ax.add_patch(plt.Rectangle((0,0),390,390,fill=False,ls='--',ec='#777',label='Nominal tabletop FOV'))
    layout=plans[1]['layout']
    for pt,c,label in zip(layout['slots_D_mm'],['#db3c30','#c59c00','#226fb2'],['Red','Yellow','Blue']):
        ax.add_patch(plt.Rectangle((pt[0]-15,pt[1]-15),30,30,fc=c,alpha=.85));ax.text(pt[0],pt[1]+22,label,ha='center',fontsize=9)
    ax.scatter(*layout['base_axis_D_xy_mm'],s=100,color='#333');ax.text(600,25,'Base')
    ax.scatter(195,195,s=100,marker='x',color='black');ax.text(180,210,'OV5640 z333',ha='right')
    ax.set(xlim=(-15,700),ylim=(-15,415),xlabel='Desk X (mm)',ylabel='Desk Y (mm)',title='Four banks / three-color complete routes')
    ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(loc='lower left',fontsize=8)
    zoom.set(xlim=(100,315),ylim=(162,203),xlabel='Desk Y (mm)',ylabel='TCP Z (mm)',title='PRE follow span 160mm / delivery heights unchanged')
    zoom.grid(alpha=.2);zoom.legend(loc='upper center',ncol=2,fontsize=8)
    for ext in ('png','svg','pdf'):fig.savefig(out/('mode_a_four_paths.'+ext),dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(7.2,4.5),layout='constrained')
    for i in range(4):
        y0=16+24*i;bank=3-i
        ax.add_patch(plt.Rectangle((0,y0),128,24,fc=colors[bank],alpha=.2))
        ax.text(64,y0+12,f'Image band {i+1} -> bank{bank}, H Y={t["banks"][bank]["H"][1]} mm',ha='center',va='center')
    for y in (16,40,64,88,112):ax.axhline(y,color='#555',ls='--',lw=.6)
    ax.set(xlim=(0,128),ylim=(128,0),xlabel='Locator center X',ylabel='Locator center Y',title='Fixed thresholds / image up -> desk +Y')
    for ext in ('png','svg','pdf'):fig.savefig(out/('mode_a_four_regions.'+ext),dpi=180)
    plt.close(fig)
    lines=['# 最新路径规划 v0.10.0：四区跟手','','四个水平图像区域以定位框中心直接比较，阈值40/64/88，不做实体采样；图像上方→桌面+Y。相机(195,195,333)mm、名义桌面视域390×390mm；掌面150mm处针孔估计宽214.32mm，四个中心取整为Y=115/170/220/275mm。','','![全部路径](figures/mode_a_four_paths.png)','','![区域阈值](figures/mode_a_four_regions.png)','','| bank | 画面Y | PRE mm | H mm | H_CLEAR mm | 红/黄/蓝插补秒 |','|---|---|---|---|---|---|']
    for i,p in enumerate(plans):
        c=p['layout']['common_D_mm'];lines.append(f'|{i}|{88-24*i}～{111-24*i}|{c["PRE"]}|{c["H"]}|{c["H_CLEAR"]}|'+ '/'.join(f'{r["seconds"]:.2f}' for r in p['paths'])+'|')
    lines+=['','每bank 47关键点/59共享段/最大归还栈23。上述为插补时间，不含启动接HOME、段末停稳、PRE最少2秒/PALM0.5秒及人的等待。完整时序分解见各bank/SUMMARY.json。','','H X=285、PRE X=350用于扩大Y范围后的可达性；各高度保持175/180/195mm。三块、B、抓取段及600/27、50Hz保持。最上bank3工具倾角在H为35°，沿175→195mm退爪路径渐变回40°；其他三区40°。初次40°版本在最高Y末端出现约0.07mm名义掌面穿入，失败结果保留，最终候选已修改并独立回放。','','| 起点bank → 终点bank |0|1|2|3|','|---|---|---|---|---|']
    for a in range(4):lines.append('|'+str(a)+'|'+'|'.join(f'{t["align_pairs"][4*a+b]["seconds"]:.2f}s' for b in range(4))+'|')
    lines+=['','局部跟随使用各起止bank的N/Na；候选至少120ms/3帧、每次对齐停稳160ms。运动中刷新最新候选，当前段完成后使用。全局最长N/Na仅作归还锚点。没有连续在线IK或中途改写段目标。','','HOME开爪→槽上方→下降→夹紧→同XY抬升→B→初始bank1 PRE→按区域跟随到目标PRE→同区PALM锁定→8段递送→开爪→2段退爪→HOME。FIST持续1秒在释放提交前触发，逆行局部未完成段→当前PRE→初始PRE→原槽放回→HOME，恢复库存。','','各bank/JOINT_TARGETS_NATIVE.csv给出六轴原生弧度、点位及段时长，PLAN_NATIVE.json含精确S2 Q16采样，S4_BANKED_CANDIDATE.json是下载配置。cancel_replay是实际FSM发出目标的16路回放，覆盖12次正常任务和4种归还情景。','','残差沿用已通过A点参考，不构成新的实体映射。Coppelia为停止运动学、12个机械臂网格与旋转附着，包含桌面/相机/另两物块/掌面代理，未模拟接触动力学和舵机误差；本版实体NOT_RUN。']
    (root/'PATH_PLAN_CN.md').write_text('\n'.join(lines)+'\n','utf-8')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);main(ap.parse_args().candidate)
