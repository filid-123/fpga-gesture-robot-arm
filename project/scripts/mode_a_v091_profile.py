"""Image top/middle/bottom mapped to fixed desk-Y banks; unchanged motion limits."""
from mode_a_v2_profile import segment,retime,profile as parent_profile
from mode_a_speed15_profile import SPEED,ACC

def profile():
 p=parent_profile();p.update(version='0.9.1',handalign_image_axis='Y',handalign_desk_axis='Y',handalign_height_unchanged=True,handalign_mapping='Calibrated image-Y cells; desk-Y -20/0/+20 mm, PALM locks then blind delivery')
 return p
