"""Derive the board bridge from the proven PS/CPU startup/restoration path."""
from pathlib import Path
import argparse,hashlib,json
from mode_a_board_config import backend_writes,task_writes,vision_writes,ARM,PLAN,TASK,VIS,ROOT
from mode_a_terminal import ADDRS


def generate(plan,table):
    original=ROOT/'scripts/mode_a_camera_v3_v0_4_0/jtag_bridge.tcl'
    text=original.read_text('utf-8').replace('0x43C50010 0x3404','0x43C50010 0x3405')
    text=text.replace('v0.2.5 operator-controlled continuous LED camera-only session, arm disconnected and D5 low',
        'v0.7.2 operator-authorized preconnected D5; initial backend OFF, LINE query with ARM=0 before motion')
    read=sorted(set(ADDRS+[ARM+4,VIS+0xc,VIS+0x10,VIS+0x14,VIS+0x18,VIS+0x1c,VIS+0x88,VIS+0x8c,VIS+0x90,VIS+0x94]))
    write=sorted(set(a for a,v in backend_writes(plan)+task_writes(plan,table)+vision_writes())|{ARM,ARM+4,PLAN,PLAN+0x18,TASK,TASK+0x58,VIS+0x88})
    write+= [PLAN+o for o in (0x40,0x44,0x48,0x4c,0x50)]
    write+= [PLAN+0x100+32*i+o for i in range(6) for o in (0,4,8,12)]
    prefix='set board_read {'+' '.join(hex(a) for a in read)+'}\nset board_write {'+' '.join(hex(a) for a in sorted(set(write)))+'}\nset board_telemetry {'+' '.join(hex(a) for a in ADDRS)+'}\nset board_started 0\n'
    # Host writes are blocked while S4 owns motion. The PL refreshes its own
    # feedback snapshots then; only capture from the host before ownership.
    prefix+='''proc board_boot_guard {status mode task_status} {
    if {($mode & 0x103) || ($status & 0x3006) || ($task_status & 128)} {
        error "Require backend OFF/unarmed/idle and no S4 owner before setup"
    }
    if {!($status & 8)} {error "D5 not high at launch; exit and preconnect D5 before next run"}
}
proc board_telemetry_snapshot {} {
    global board_telemetry
    if {!([rd 0x43C50004] & 128)} {wr 0x43C30000 4}
    set data {}
    foreach a $board_telemetry {lappend data [format 0x%08X [rd $a]]}
    return $data
}
'''
    text=prefix+text
    old='    if {[rd 0x43C30008]&12} {error "D5 must stay low; physical permission must be absent"}'
    if old not in text:raise ValueError('Expected legacy D5 launch guard')
    text=text.replace(old,'''    board_boot_guard [rd 0x43C30008] [rd 0x43C30004] [rd 0x43C50004]
    say "D5_PRECONNECTED_BACKEND_OFF_CONFIRMED"''')
    text=text.replace('    global ps_read ps_write ids','    global ps_read ps_write ids board_write')
    text=text.replace('    error [format "Address denied:', '    if {$writing && [lsearch -exact $board_write [format 0x%x $a]]>=0} {return}\n    error [format "Address denied:')
    start=text.index('proc host_read_guard');end=text.index('proc stream_guard',start)
    text=text[:start]+'''proc host_read_guard {a} {
    global board_read
    if {![string is wideinteger -strict $a] || ($a & 3) || [lsearch -exact $board_read [format 0x%x $a]]<0} {error "Unmapped board read"}
}
proc host_guard {a v} {
    global board_write
    if {![string is wideinteger -strict $a] || ![string is wideinteger -strict $v] || $v<0 || $v>0xffffffff || [lsearch -exact $board_write [format 0x%x $a]]<0} {error "Unmapped board write"}
    if {$a==0x43c30004 && $v ni {0 1 2 3 259}} {error "Backend mode denied"}
    if {$a==0x43c50000 && $v ni {1 2 8 64 2048}} {error "Only enable/release/cancel/abort/restock; no PS task selection"}
    if {$a==0x43c40000 && $v ni {1 8 16}} {error "Planner command denied"}
    if {$a==0x43c60088} {
        if {$v & 0x7f000000} {error "Sensor reserved bits"}
        set r [expr {($v>>8)&65535}]
        if {($v & 0x80000000) ? (($v&255)!=0) : ($r ni {13568 13569 13570 13571 13578 13579})} {error "Sensor command denied"}
    }
}
''' +text[end:]
    start=text.index('if {[lindex $argv 0] eq "--check-only"}');end=text.index('if {[llength $argv]!=4',start)
    text=text[:start]+'''if {[lindex $argv 0] eq "--check-only"} {
    foreach a $board_read {host_read_guard $a}
    foreach pair {{0x43c30004 259} {0x43c50000 1} {0x43c50000 2048} {0x43c60088 0x80350300}} {host_guard {*}$pair}
    foreach pair {{0x43c50060 1} {0x43c50000 4} {0x43c50000 3} {0xF8000240 0} {0x43c30004 -1} {0x43c60088 0x00380001}} {
        if {![catch {host_guard {*}$pair}]} {error "Forbidden command accepted"}
    }
    say "OFFLINE_BOARD_GUARDS_PASS_NO_HARDWARE"
    exit 0
}
''' +text[end:]
    text=text.replace('global saved cpu_saved modified stopped was_running\n','global saved cpu_saved modified stopped was_running board_started bus_fault\n')
    marker='    if {$modified} {\n'
    shutdown='''    if {$board_started && !$bus_fault} {
        set s [rd 0x43C50004]
        if {$s & 128} {
            wr 0x43C50000 64
            after 50
            wr 0x43C50000 2
            after 50
            if {[rd 0x43C50004] & 128} {error "Task ownership not released; remove D5/power"}
        }
        wr 0x43C30004 0
        wr 0x43C40000 8
        say "BOARD_BACKEND_OFF_AND_OWNERSHIP_RELEASED"
    }
'''
    text=text.replace(marker,shutdown+marker,1)
    text=text.replace('    say "JTAG_READY"','    set board_started 1\n    say "JTAG_READY"')
    marker='                W {\n'
    cases='''                B {
                    if {[llength $line]<4 || ([llength $line]%2)!=0 || [llength $line]>130} {error "Bad write batch"}
                    foreach {a v} [lrange $line 2 end] {host_guard $a $v;wr $a $v}
                    set data WRITTEN
                }
                T {
                    set data [board_telemetry_snapshot]
                }
'''
    text=text.replace(marker,cases+marker,1)
    return text,dict(parent_bridge_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),read_addresses=read,write_addresses=sorted(set(write)),telemetry_addresses=ADDRS)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    text,meta=generate(json.loads((a.candidate/'PLAN_NATIVE.json').read_text('utf-8')),json.loads((a.candidate/'S4_NATIVE_CANDIDATE.json').read_text('utf-8')))
    with a.out.open('x',encoding='utf-8') as f:f.write(text)
    a.out.with_suffix('.json').write_text(json.dumps(meta,indent=2)+'\n','utf-8')
