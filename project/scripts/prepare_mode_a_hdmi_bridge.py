"""Same target-bound bridge and whitelist as v0.11.1."""
from prepare_mode_a_palmfix_bridge import generate as parent_generate

def generate(plan,table):
 text,meta=parent_generate(plan,table);return text.replace('v0.11.1','v0.12.0'),dict(meta,display='PASSIVE_PL_HDMI_OUT')
