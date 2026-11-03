"""Pure register images for user-authorized ABI3406 board bring-up.

Uses native user-tested command vocabulary. Does not fabricate a firmware ID,
measured calibration or completion of new raised-height physical tests.
"""
from pathlib import Path
import math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ps/robot'))
from arm_backend import PlBackendConfig,JsonPlConfig
from arm_backend_axi_driver import ArmBackendAxiDriver
from arm_fixed_point import ChannelMap,rad_to_q16_16
from arm_frame_template import TemplateImage
from roarm_json_reference import RoArmJsonProtocol,JsonParserConfig,compile_template
from mode_a_follow_profile import SPEED,ACC,profile
ARM=0x43c30000;PLAN=0x43c40000;TASK=0x43c50000;VIS=0x43c60000


def protocol():
    return RoArmJsonProtocol(path=None,protocol_id='user_tested_native_t102_t105_v082',status='VERIFIED',fixture=False,
        firmware_version=None,sources=(),line_terminator=b'\n',fraction_digits=4,
        commands=dict(set_joints='{"T":102,"base":${ch0},"shoulder":${ch1},"elbow":${ch2},"wrist":${ch3},"roll":${ch4},"hand":${ch5},"spd":'+str(SPEED)+',"acc":'+str(ACC)+'}',feedback_request='{"T":105}'),
        discriminator_key='T',discriminator_value=1051,position_keys=('b','s','e','t','r','g'),feedback_fraction_digits=4,max_line_length=512)


def backend_config(plan):
    p=protocol();image=TemplateImage.build(compile_template(p,'set_joints'),compile_template(p,'feedback_request'))
    maps=tuple(ChannelMap(rad_to_q16_16(lo),rad_to_q16_16(hi),0,10000*65536,False,i,400 if i==5 else 200) for i,(lo,hi) in enumerate(plan['native_limits_rad']))
    return PlBackendConfig(backend_sel=0,channel_maps=maps,template=image,baud_div_roarm=868,baud_div_bus=100,
        hd_lead_cycles=0,hd_lag_cycles=0,response_timeout_cycles=0,wd_prescale=100000,feedback_timeout_ticks=500,
        arrival_count=3,required_mask=63,prime_period_cycles=10_000_000,reads_per_cycle=6,json=JsonPlConfig(JsonParserConfig.from_protocol(p)),
        source='Operator reports v0.8.0 test passed; geometry reused, new PRE shift and cancel return not yet physically tested')


def backend_writes(plan):
    class Record:
        def __init__(self):self.rows=[]
        def read(self,o):return 0
        def write(self,o,v):self.rows.append([ARM+o,int(v)&0xffffffff])
    r=Record();ArmBackendAxiDriver(r).load_config(backend_config(plan));return r.rows


def task_writes(plan,table):
    pr=profile();q=lambda v:int(v)&0xffffffff
    w=[(0x24,0x000e8102),(0x28,100000),(0x2c,pr['palm_hold_ms']),(0x30,0),(0x34,pr['palm_loss_periods']),(0x38,0),(0x3c,500),(0x40,10000),(0x44,0),
       (0x48,50),(0x4c,2_000_000),(0x50,50_000_000),(0x54,(table['home_kp']<<8)|(table['predelivery_kp']<<16))]
    for i,(lo,hi) in enumerate(plan['native_limits_rad']):
        w += [(0x80+4*i,q(rad_to_q16_16(lo))),(0x98+4*i,q(rad_to_q16_16(hi)))]
    v=math.ceil(math.radians(pr['planned_speed_deg_s'])*.02*65536)+2
    a=math.ceil(math.radians(max(160,pr['planned_acceleration_deg_s2']))*.02**2*(1<<32))+2
    for i in range(6):
        cv=math.ceil(math.radians(pr['gripper_speed_deg_s'])*.02*65536)+2 if i==5 else v
        ca=math.ceil(math.radians(pr['gripper_acceleration_deg_s2'])*.02**2*(1<<32))+2 if i==5 else a
        w +=[(0xb0+4*i,cv),(0xc8+4*i,ca)]
    w +=[(0x124,pr['fist_hold_ms']),(0x128,pr['predelivery_wait_ms'])]
    w.append((0x110,0))
    for kp in table['keypoints']:
        for value in kp:w.append((0x114,q(value)))
    w.append((0x118,0))
    for kp,n,na,prof,flags in table['segments']:w +=[(0x11c,(flags<<24)|(prof<<16)|kp),(0x11c,(na<<16)|n)]
    keys=[f'{ph}_{obj}' for ph in ('approach','grasp','lift') for obj in (1,2,3)]+['deliver','release','retreat']
    for i,key in enumerate(keys):
        first,count=table['descriptors'][key];w.append((0xe0+4*i,(count<<8)|first))
    return [[TASK+o,v] for o,v in w]


def vision_writes():
    # Fixed full letterbox-content region for this first raised-height board trial.
    # Pixel-to-palm-plane geometry is not independently calibrated.
    return [[VIS+0x10,0|(128<<16)],[VIS+0x14,16|(112<<16)],[VIS+0x18,3],[VIS+0x1c,25_000_000],[VIS+0xc,3|(3<<8)]]
