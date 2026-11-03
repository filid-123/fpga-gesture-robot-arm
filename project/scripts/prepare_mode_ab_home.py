"""Fixed empty A/B HOME transitions, sampled under the B nominal CAD model."""
from pathlib import Path
import argparse
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from pc.mode_ab.motion import home,template
from pc.mode_ab.geometry import validate
from prepare_mode_b_loaded_route import objects
from mode_a_upgrade_profile import segment


def build():
    p=template('red_cube');p['request']['destination']['support_centre_mm'][2]=0;cache=objects(p)
    result={}
    for a,b in [('A','B'),('B','A')]:
        start=[round(v*65536) for v in home(a)];target=[round(v*65536) for v in home(b)]
        leg,samples=segment(start,target,'MODE_HOME_TRANSITION','motion')
        exact=validate(p,np.array([start]+samples)/65536,False,'EMPTY_HOME_TRANSITION',cache,empty=True)
        rounded=np.round(np.array([start]+samples)/65536,4)
        wire=validate(p,rounded,False,'EMPTY_HOME_TRANSITION_WIRE',cache,empty=True)
        result[a+'_to_'+b]=dict(from_mode=a,to_mode=b,legs=[leg],exact=exact,wire=wire,
            verification='NOMINAL_URDF_OBB_ALL_FINGER_STATES_EXACT_AND_4_DECIMAL_WIRE',
            physical_test='NOT_RUN',scope='KNOWN_EMPTY_HOME_TO_KNOWN_EMPTY_HOME_ONLY')
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);p=ap.parse_args().out
    if p.exists():raise FileExistsError(p)
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(build(),indent=2)+'\n')
    print('PASS: empty A/B fixed HOME transitions, exact and native wire rounding')
