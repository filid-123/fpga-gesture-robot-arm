"""Local-only diagrams for the operator; generated from candidate data."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Circle
from matplotlib.font_manager import FontProperties


def render(candidate,out):
    out.mkdir(parents=True,exist_ok=False)
    layout=json.loads((candidate/'LAYOUT.json').read_text('utf-8'));preview=json.loads((candidate/'PATH_PREVIEW.json').read_text('utf-8'))
    font=FontProperties(fname=r'C:\Windows\Fonts\msyh.ttc');plt.rcParams['font.family']=font.get_name();plt.rcParams['axes.unicode_minus']=False
    colors=['#d84e56','#cf9b11','#387ed2'];fig,ax=plt.subplots(figsize=(12,8.5));fig.patch.set_facecolor('#f7f9fc');ax.set_facecolor('#fff')
    ax.add_patch(Rectangle((0,0),800,600,fill=False,linewidth=2,color='#253a54'))
    ax.add_patch(Rectangle((0,0),310,310,facecolor='#e1f0f7',edgecolor='#4387a4',alpha=.65,linestyle='--',linewidth=1.8))
    ax.text(15,295,'操作者给定的桌面视域\n0–310 mm × 0–310 mm',va='top',fontsize=11,color='#24576f')
    for path,color in zip(preview['paths'],colors):
        rows=[r for r in path['rows'] if r['phase'] in ('lift','deliver')];ax.plot([r['D_mm'][0] for r in rows],[r['D_mm'][1] for r in rows],color=color,lw=2,alpha=.8)
    for i,(p,color) in enumerate(zip(layout['slots_D_mm'],colors),1):
        ax.add_patch(Rectangle((p[0]-15,p[1]-15),30,30,facecolor=color,edgecolor='#26354a'));ax.text(p[0],p[1]+28,f'{["红","黄","蓝"][i-1]} {p[:2]}',ha='center',fontsize=11)
    base=layout['base_axis_D_xy_mm'];ax.add_patch(Circle(base,30,facecolor='#bdc7d3',edgecolor='#33465e'));ax.text(base[0],base[1]+45,'轴心 (585,25)',ha='center',fontsize=11)
    for label,offset in [('INNER',(12,-22)),('B',(12,18)),('PRE',(8,32)),('H',(-110,-40))]:
        p=layout['common_D_mm'][label];ax.scatter(*p[:2],color='#594b87',s=28,zorder=4)
        ax.annotate(f'{label} ({p[0]},{p[1]},{p[2]})',p[:2],xytext=(p[0]+offset[0],p[1]+offset[1]),arrowprops=dict(arrowstyle='-',color='#766a94'),fontsize=10)
    hp=layout['common_D_mm']['H'];ax.add_patch(Rectangle((hp[0]-40,hp[1]-40),80,80,facecolor='#80b997',alpha=.24,edgecolor='#5a9771'))
    c=layout['camera']['lens_D_mm'];ax.plot(c[0],c[1],marker='x',markersize=10,mew=2.8,color='#234d8d')
    ax.annotate('OV5640 (195,195,333)\n镜头向下，视域按现场给定',c[:2],xytext=(30,360),arrowprops=dict(arrowstyle='-',color='#234d8d'),fontsize=11,color='#234d8d')
    tilt=layout['delivery_pose']['tilt_deg_at_x_le_270'];palm=layout['palm_surface_candidate_z_mm'];clear=layout['common_D_mm']['H_CLEAR'][2]
    ax.text(360,535,f'三块和底座保持原位\nB → PRE → H 重新反解\n抓取竖直 / 交付末端倾斜{tilt}°\n掌面参考 Z={palm} mm，H_CLEAR Z={clear} mm',fontsize=12,va='top',linespacing=1.8)
    ax.set(xlim=(-25,825),ylim=(-25,625),xlabel='桌面 X / mm →',ylabel='桌面 Y / mm →');ax.set_aspect('equal');ax.grid(alpha=.17)
    ax.set_title('模式 A · 相机位置与三色交付路线',fontsize=18,pad=18)
    fig.text(.5,.018,'原桌面左前角为原点；图中为候选运动学路径。相机识别手势，三块可在视域外。',ha='center',fontsize=10,color='#45556b')
    fig.tight_layout(rect=(0,.035,1,1))
    for suffix in ('png','pdf','svg'):fig.savefig(out/f'LAYOUT_AND_PATHS.{suffix}',dpi=160)
    plt.close(fig)
    fig=plt.figure(figsize=(12,8));ax=fig.add_subplot(111,projection='3d')
    for path,color in zip(preview['paths'],colors):
        rows=[r for r in path['rows'] if r['phase'] in ('approach','grasp','lift','deliver','release') and not r['label'].startswith(('HOME','INNER_FROM_HOME'))]
        ax.plot([r['D_mm'][0] for r in rows],[r['D_mm'][1] for r in rows],[r['D_mm'][2] for r in rows],color=color,lw=1.8,label=['红','黄','蓝'][path['object']-1])
    for label in ('INNER','B','PRE','H','H_CLEAR'):
        p=layout['common_D_mm'][label];ax.scatter(*p,color='#564578',s=20);ax.text(*p,label)
    ax.set(xlabel='桌面 X / mm',ylabel='桌面 Y / mm',zlabel='Q高度 Z / mm',zlim=(0,max(190,clear+30)));ax.view_init(elev=26,azim=-64);ax.legend();ax.set_title('三色实际 S2 插补轨迹 · 抓取到交付',fontsize=17)
    fig.tight_layout()
    for suffix in ('png','pdf'):fig.savefig(out/f'THREE_COLOR_3D.{suffix}',dpi=150)
    plt.close(fig)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();render(a.candidate,a.out)
