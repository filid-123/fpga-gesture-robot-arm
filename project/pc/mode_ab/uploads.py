"""Sparse writes of an exactly tracked S4 RAM image, through existing ports.

No register/ABI changes. The sole board owner tracks successful transactions.
Any uncertain write invalidates the image and stops the session. Unchanged RAM
words are reused; all changed words and bank readiness sentinels are written.
"""
from copy import deepcopy
from pc.mode_ab.registers import TASK


class TableImage:
    def __init__(self):
        self.kp=[[None]*512 for _ in range(4)];self.seg=[None]*256;self.bank=None

    def plan(self,rows):
        image=deepcopy(self);out=[];i=0
        while i<len(rows):
            address,value=rows[i];value&=0xffffffff
            if address==TASK+0x12c:
                if value not in range(4):raise ValueError('Invalid keypoint bank')
                image.bank=value
            if address in (TASK+0x110,TASK+0x118):
                keypoint=address==TASK+0x110;port=TASK+(0x114 if keypoint else 0x11c)
                if keypoint and image.bank is None:raise ValueError('Keypoint bank is unknown')
                memory=image.kp[image.bank] if keypoint else image.seg
                cursor=value;changed=set();j=i+1
                while j<len(rows) and rows[j][0]==port:
                    if cursor>=len(memory):raise ValueError('Table write exceeds physical RAM')
                    word=rows[j][1]&0xffffffff
                    if memory[cursor]!=word:changed.add(cursor)
                    memory[cursor]=word;cursor+=1;j+=1
                if j==i+1:
                    out.append([address,value]);i=j;continue
                if changed and keypoint:
                    # Real S4 clears readiness on word 0 and sets it on 511.
                    if memory[0] is None or memory[511] is None:raise ValueError('Partial bank lacks known readiness sentinels')
                    changed.update((0,511))
                previous=None
                for index in sorted(changed):
                    if previous is None or index!=previous+1:out.append([address,index])
                    out.append([port,memory[index]]);previous=index
                i=j;continue
            if address in (TASK+0x114,TASK+0x11c):raise ValueError('Table data without explicit cursor')
            out.append([address,value]);i+=1
        return out,image


def home_b_writes(q):
    """Only point zero can execute before a fresh dynamic path is committed."""
    rows=[]
    for bank in range(4):
        rows += [[TASK+0x12c,bank],[TASK+0x110,0]]+[[TASK+0x114,v] for v in q+[0,0]]
        rows += [[TASK+0x110,511],[TASK+0x114,0]]
    return rows
