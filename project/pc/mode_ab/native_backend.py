"""Additional native B formatter programs; the original A program is intact."""
import re
from pc.mode_ab.registers import ARM

def assemble(text):
    words=[]
    for part in re.split(r'(\$\{(?:ch[0-5]|speed|acc)\})',text):
        if part.startswith('${'):
            token=part[2:-1]
            words.append(0x2000|({'speed':6,'acc':7}.get(token,int(token[2:]) if token.startswith('ch') else 0))|(0x40 if token.startswith('ch') else 0))
        else:words.extend(0x1000|b for b in part.encode('ascii'))
    return words+[0]

def programs():
    motion=assemble('{"T":102,"base":${ch0},"shoulder":${ch1},"elbow":${ch2},"wrist":${ch3},"roll":${ch4},"hand":${ch5},"spd":${speed},"acc":${acc}}\n')
    grip=assemble('{"T":106,"cmd":${ch5},"spd":${speed},"acc":${acc}}\n')
    if len(motion)>96 or len(grip)>48:raise ValueError('B formatter program capacity')
    return {112:motion,208:grip}

def extra_writes():
    return [row for base,words in programs().items() for row in [[ARM+0x40,base]]+[[ARM+0x44,w] for w in words]]

def backend_writes(plan):
    from mode_a_restock_config import backend_writes as original
    return original(plan)+extra_writes()
