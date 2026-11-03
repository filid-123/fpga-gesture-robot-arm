"""Keep raw tracking; S4 cell/freshness supplies PALM spatial admission."""
from mode_a_follow_config import ROOT,ARM,PLAN,TASK,VIS,backend_config,backend_writes,task_writes,protocol,default_map,validate_map,preview_band
from mode_a_follow_config import vision_writes as parent_vision_writes

def vision_writes():
    # Raw network boxes are clipped to0..128 and may extend into letterbox padding.
    # S4 already requires the fresh detected center in the accepted16..111 cell,
    # PRE2s and PALM500ms. Keep the adapter's3-frame class/detection confirmation,
    # while removing the old whole-box containment/corner-motion restriction.
    replacements={VIS+0x14:0|(128<<16),VIS+0x18:128}
    return [[a,replacements.get(a,v)] for a,v in parent_vision_writes()]
