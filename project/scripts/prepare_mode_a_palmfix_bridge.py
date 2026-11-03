"""Unchanged target-bound bridge; admit only the existing configuration addresses."""
from prepare_mode_a_follow_bridge import generate as parent_generate

def generate(plan,table):
    text,meta=parent_generate(plan,table)
    meta=dict(meta,palm_window_policy='RAW_BOX_FULL0_128; center-cell/freshness checked in S4; three adapter frames and PRE2s/PALM500ms retained')
    return text.replace('v0.11.0','v0.11.1'),meta
