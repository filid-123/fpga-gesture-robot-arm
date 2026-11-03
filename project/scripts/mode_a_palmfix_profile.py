"""v0.11.1 changes PALM admission only; motion remains exactly v0.11.0."""
from mode_a_follow_profile import segment,retime,SPEED,ACC,profile as parent_profile

def profile():
    p=parent_profile()
    p.update(version='0.11.1',palm_admission='Qualified fresh PALM plus accepted current Locator center cell; raw box extent/size is not a delivery-position condition')
    return p
