"""Bounded offline image transfer into the locked B program store."""
from pc.mode_ab.native_routes import program_hash
import time
ROUTE=0x43c20000

def upload(board,program):
    started=time.perf_counter();digest=program_hash(program)
    if program['abi']!=0xb001 or program['stage_count']!=16 or len(program['offsets'])>2048:raise ValueError('Wrong native program')
    if board.b.read(ROUTE+12)[0]!=0xb001:raise RuntimeError('BIT 缺少 B 原生轨迹能力；请使用同包 ABI340E BIT')
    if getattr(board,'native_program_digest',None)==digest and board.b.read(ROUTE+4)[0]&1 and board.b.read(ROUTE+8)[0]==0:
        return dict(points=len(program['offsets']),hash=digest,confirmed_same_owner_reuse=True,actual_program_words_written=0,elapsed_ms=(time.perf_counter()-started)*1000)
    board.native_program_digest=None
    board.b.write(ROUTE,1);board.b.write(ROUTE+28,16)
    planes=[[row[ch]&0xffffffff for row in program['offsets']] for ch in range(6)]
    planes += [[v&0xffffffff for v in program['descriptors']],[v&0xffffffff for v in program['bases']]]
    for plane,values in enumerate(planes):
        board.b.write(ROUTE+16,plane)
        for start in range(0,len(values),32):
            board.alive();board.heartbeat();chunk=values[start:start+32]
            board.b.write(ROUTE+20,start)
            board.b.call('U '+str(ROUTE+128)+' '+' '.join(map(str,chunk)))
            actual=[int(x,0) for x in board.b.call('V '+str(ROUTE+128)+' '+str(len(chunk))).split()]
            if actual!=chunk:raise RuntimeError(f'B 原生轨迹 RAM 回读不符：plane={plane}, offset={start}；未提交，不允许启动')
    board.b.write(ROUTE,2)
    if board.b.read(ROUTE+4)[0]&1!=1 or board.b.read(ROUTE+8)[0]!=0:raise RuntimeError('B 原生轨迹完整提交失败')
    board.native_program_digest=digest
    return dict(points=len(program['offsets']),hash=digest,all_words_read_back=True,confirmed_same_owner_reuse=False,
        actual_program_words_written=sum(map(len,planes)),elapsed_ms=(time.perf_counter()-started)*1000)

def extend_bridge(text):
    # XSDB maintains its own PL access map, independently of the XSA/HWH and
    # the Tcl host whitelist. Register the new physical 4 KiB page before any
    # ID or telemetry read; do not disable XSDB's memory-access protection.
    load='loadhw -hw $xsa -mem-ranges [list '
    if text.count(load)!=1 or text.count('set ids {')!=1:
        raise ValueError('Native startup bridge template changed: loadhw/ABI list missing')
    text=text.replace(load,load+'{0x43C20000 0x43C20FFF} ',1)
    text=text.replace('set ids {','set ids {0x43C2000C 0xB001 ',1)
    text=text.replace('MATCHING_XSA_FOUR_PL_PAGES_LOADED','MATCHING_XSA_FIVE_PL_PAGES_LOADED')
    text=text.replace('ALL_FOUR_ABIS_AND_MODEL_ID_PASS','ALL_FIVE_ABIS_AND_MODEL_ID_PASS')
    offsets=(0,4,8,12,16,20,28,*range(128,256,4))
    text=text.replace('set board_read {','set board_read {'+' '.join(hex(ROUTE+o) for o in offsets)+' ')
    text=text.replace('set board_write {','set board_write {'+' '.join(hex(ROUTE+o) for o in (0,16,20,28))+' ')
    anchor='    if {$a==0x43c30004'
    guard='''    if {$a>=0x43c20000 && $a<0x43c20100} {
        route_upload_guard
        if {$a==0x43c20000 && $v ni {1 2}} {error "Native program command denied"}
        if {$a==0x43c20010 && $v>7} {error "Native plane denied"}
        if {$a==0x43c20014 && $v>2047} {error "Native offset denied"}
        if {$a==0x43c2001c && $v!=16} {error "Native stage count denied"}
    }
'''
    i=text.index(anchor);text=text[:i]+guard+text[i:]
    prefix='''proc route_upload_guard {} {
    set s [rd 0x43c50004]
    if {($s & 15)!=2 || !([rd 0x43c50024]&1)} {error "Native program requires stationary B WAIT_PATH"}
    if {[rd 0x43c50010]!=0x340e || [rd 0x43c2000c]!=0xb001} {error "Native program ABI mismatch"}
}
proc route_bulk_guard {a count} {
    if {![string is wideinteger -strict $a] || $a<0x43c20080 || ($a&3) || ![string is integer -strict $count] || $count<1 || $count>32 || $a+4*$count>0x43c20100} {error "Native bulk window denied"}
    route_upload_guard
    if {[rd 0x43c20014]+(($a-0x43c20080)/4)+$count>2048} {error "Native RAM overrun"}
}
'''
    cases='''                U {
                    set a [lindex $line 2];set values [lrange $line 3 end]
                    route_bulk_guard $a [llength $values]
                    foreach v $values {if {![string is wideinteger -strict $v] || $v<0 || $v>0xffffffff} {error "Native word denied"}}
                    if {[catch {mwr -address-space PA -bypass-cache-sync -size w $a $values} problem]} {set bus_fault 1;error $problem}
                    set data WRITTEN
                }
                V {
                    if {[llength $line]!=4} {error "Bad native read request"}
                    set a [lindex $line 2];set count [lindex $line 3]
                    route_bulk_guard $a $count
                    if {[catch {mrd -address-space PA -value -size w $a $count} values]} {set bus_fault 1;error $values}
                    if {[llength $values]!=$count} {set bus_fault 1;error "Short native RAM read"}
                    set data {};foreach v $values {lappend data [format 0x%08X [u32 $v]]}
                }
'''
    marker='            switch -- $op {\n';assert text.count(marker)==1
    return prefix+text.replace(marker,marker+cases)
