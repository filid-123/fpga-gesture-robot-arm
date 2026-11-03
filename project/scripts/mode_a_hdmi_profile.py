"""HDMI is passive; all v0.11.1 control and motion values remain unchanged."""
from mode_a_palmfix_profile import profile as parent_profile,segment

def profile():
 p=parent_profile();p.update(version='0.12.0',display='640x480/60Hz HDMI OUT; one frame-matched Locator box and Chinese gesture/command/state cards');return p
