"""Four image-Y bands, nominal camera projection and live PL target mailbox."""
from mode_a_v091_profile import segment,retime,profile as parent_profile
from mode_a_speed15_profile import SPEED,ACC
H_Y=[115,170,220,275]

def profile():
 p=parent_profile();p.update(version='0.10.0',task_abi=0x3408,handalign_regions=4,handalign_hold_ms=120,handalign_min_frames=3,handalign_mapping='Fixed image-Y thresholds40/64/88; upper image maps desk+Y; no physical sampling',handalign_offsets_mm=None,handalign_live_mailbox=True,handalign_settle_ms=160,handalign_pair_specific_timing=True,camera_view_table_mm=390,palm_plane_mm=150,handalign_H_y_mm=H_Y,handalign_H_x_mm=285,handalign_PRE_x_mm=350)
 return p
