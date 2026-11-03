"""ABI340D host images. All task selection remains in the PL gesture path."""
import math
from pc.mode_ab.motion import ROOT
import sys
sys.path.insert(0,str(ROOT/'scripts'))
from mode_a_restock_config import ARM,PLAN,TASK,VIS,task_writes as a_writes
from mode_a_upgrade_config import default_map
from run_mode_a_restock import ADDRS as A_ADDRS
from mode_a_terminal import decode

ROUTE=0x43c20000
ADDRS=list(dict.fromkeys(A_ADDRS+[TASK+o for o in (0x24,0x54,0x5c,0x64,0x38c,0x390)]+[ROUTE+8]))


def snapshot(raw):
    s=decode(raw,task_abi=0x340e,planner_abi=0x3203,vision_abi=0x3506)
    r={int(k,0) if isinstance(k,str) else k:int(v) for k,v in raw.items()}
    s.update(abi_verified=True,done_counter=r[TASK+0x240],cancelled_counter=r[TASK+0x244],
             restocking=bool(r[TASK+4]&(1<<29)),restocked_tasks=r[TASK+0x388],
             selected_task_id=r[TASK+0x390]>>16,selected_gesture=r[TASK+0x390]&3,
             fpga_mode='B' if r[TASK+0x24]&1 else 'A',feedback_live_valid=bool(r[ARM+8]&32),
             align_step=r[TASK+0x324]&127,align_target_step=(r[TASK+0x324]>>8)&127,
             fifo_count=r[TASK+0x64]&63,fifo_overflow=bool(r[TASK+0x64]&(1<<9)),
             backend_mode=('OFF','DRY_RUN','MONITOR','LINE')[(r[ARM+8]>>12)&3])
    error=r.get(ROUTE+8,0)
    labels=('配置处于写锁状态或写事务非法','轨迹描述符或六轴基准不完整','轨迹偏移超出18位无损存储范围',
            '阶段索引、样本数、地址、周期或速度参数不合法','原生轨迹已收到停止指令','下游样本持续阻塞，超过配置的500 ms保护时间')
    s['native_route_error']=error
    s['fault_detail']='；'.join(label for bit,label in enumerate(labels) if error&(1<<bit)) if s['fpga_mode']=='B' else ''
    return s


def mode_word(mode,rows):
    select=sum(1<<r['gesture'] for r in rows)
    return (select<<16)|0x8102|(mode=='B')


def b_writes(compiled, *, restock=False):
    """WAIT_PATH-only path payload; mode, limits, perception and stocks unchanged."""
    out=[]
    for i,bank in enumerate(compiled['keypoint_banks']):
        out += [[TASK+0x12c,i],[TASK+0x110,0]]
        words=[v&0xffffffff for q in bank for v in q+[0,0]]
        out += [[TASK+0x114,v] for v in words+[0]*(512-len(words))]
    out += [[TASK+0x118,0]]
    words=[v for kp,n,na,p,f in compiled['segments'] for v in ((f<<24)|(p<<16)|kp,(na<<16)|n)]
    out += [[TASK+0x11c,v] for v in words+[0]*(128-len(words))]
    out += [[TASK+0x54,(compiled['home_kp']<<8)|(compiled['predelivery_kp']<<16)]]
    d=lambda k:(compiled['descriptors'][k][1]<<6)|compiled['descriptors'][k][0]
    for i,key in enumerate(('deliver','release','retreat'),9):
        first,count=compiled['descriptors'][key];out.append([TASK+0xe0+4*i,(count<<8)|first])
    out += [[TASK+0x300,4]]
    out += [[TASK+0x304,v] for v in (127<<9,16|(111<<9),compiled['predelivery_kp']|(d('release')<<6)|(d('deliver')<<18),d('retreat'))]
    out += [[TASK+0x308,2],[TASK+0x30c,3],[TASK+0x310,1],[TASK+0x130,(128<<16)|512]]
    out += [[TASK+0x330+4*i,(128<<16)|512] for i in range(16)]
    return out


def fifo_writes(compiled,gesture,task_id):
    out=[[TASK,512],[TASK+0x38c,int(compiled.get('restock',False))|(compiled.get('release_index',0)<<8)]]
    for row in compiled['fifo']:
        words=row['target_q16']+[(row['flags']<<24)|(row['profile']<<16),(row['na']<<16)|row['n']]
        out += [[TASK+0x68,v&0xffffffff] for v in words]
    out += [[TASK+0x5c,(task_id<<16)|gesture]]
    return out
