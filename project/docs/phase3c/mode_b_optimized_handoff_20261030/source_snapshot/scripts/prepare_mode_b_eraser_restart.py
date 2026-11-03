"""Fresh frozen eraser top, known15mm height and measured long-axis direction."""
import argparse
from pathlib import Path
from prepare_mode_b_cylinder_restart import prepare

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('capture','perception','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(a.capture,a.perception,a.output,object_name='eraser')
