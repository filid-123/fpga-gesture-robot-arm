"""Second Mode A candidate: fixed 1.5x motion, three local alignment banks."""
from mode_a_cancel_shift_profile import segment,retime,profile as first_profile
from mode_a_speed15_profile import SPEED,ACC


def profile():
    p=first_profile()
    p.update(version='0.9.0',task_abi=0x3407,release_generation=2,handalign=True,
        handalign_regions=3,handalign_hold_ms=200,handalign_min_frames=3,handalign_max_age_ms=250,
        handalign_offsets_mm=[-20,0,20],handalign_default_bank=1,
        handalign_mapping='Calibrated image-X cells; lock one bank on PALM; blind delivery thereafter')
    return p
