"""v082 keeps the tested 1.5x timing and enables return-to-slot cancellation."""
from mode_a_speed15_profile import SPEED,ACC,segment,retime,profile as speed15_profile


def profile():
    p=speed15_profile()
    p.update(version='0.8.2',cancel_policy='RETRACE_RETURN_TO_SLOT_THEN_HOME',hold_policy=False,
        pre_D_mm=[320,175,180],delivery_D_mm=[240,155,175])
    return p
