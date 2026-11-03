# v0.2.0: Phase2 small frames and constrained shared-SCCB exposure control; camera only.
# PS/PL reset release matches the same XSA ps7_post_config, full word = 0.
# Never initialize/access DDR or write PLL/MIO/UART. Physical backend modes are denied.
set saved {}
set cpu_saved {}
set modified 0
set was_running 0
set stopped 0
set bus_fault 0
set code 0
set ps_read {0xF800000C 0xF8000108 0xF800010C 0xF8000170 0xF8000174 0xF8000178 0xF800017C 0xF8000180 0xF8000184 0xF8000188 0xF800018C 0xF8000240 0xF800025C 0xF8000900}
set ps_write {0xF8000004 0xF8000008 0xF8000170 0xF8000178 0xF8000180 0xF8000188 0xF8000240 0xF8000900}
set ids {0x43C30010 0x3101 0x43C4000C 0x3202 0x43C50010 0x3404 0x43C60008 0x3505 0x43C60070 0x022267A9}
proc u32 {n} {expr {$n & 0xffffffff}}
proc say {s} {puts $s;flush stdout}
proc allowed {a writing} {
    global ps_read ps_write ids
    if {![string is wideinteger -strict $a] || ($a & 3)} {error "Invalid word address"}
    set choices [expr {$writing ? $ps_write : $ps_read}]
    foreach x $choices {if {$a==$x} {return}}
    if {!$writing} {foreach {x expected} $ids {if {$a==$x} {return}}}
    if {$writing && ($a==0x43C60040 || $a==0x43C6004C || $a==0x43C60088)} {return}
    if {!$writing} {host_read_guard $a;return}
    error [format "Address denied: 0x%08X write=%d" $a $writing]
}
proc rd {a} {
    global bus_fault
    allowed $a 0
    if {[catch {mrd -address-space PA -value -size w $a 1} values]} {set bus_fault 1;error $values}
    if {[llength $values]!=1 || ![string is wideinteger -strict [lindex $values 0]]} {set bus_fault 1;error "Malformed word read"}
    return [u32 [lindex $values 0]]
}
proc wr {a value} {
    global bus_fault
    allowed $a 1
    if {[catch {mwr -address-space PA -bypass-cache-sync -size w $a [format 0x%08X [u32 $value]]} problem]} {set bus_fault 1;error $problem}
}
proc set_checked {a value} {
    set value [u32 $value]
    wr $a $value
    set actual [rd $a]
    say [format "PS_WRITE_READBACK 0x%08X 0x%08X" $a $actual]
    if {$actual!=$value} {error "PS register readback mismatch"}
}
proc mask_checked {a mask value} {
    set_checked $a [u32 [expr {([rd $a] & ~$mask) | ($value & $mask)}]]
}
proc cpu_reg {name} {
    if {![regexp {:\s*([0-9a-fA-F]+)} [rrd $name] -> h]} {error "CPU register parse failed"}
    scan $h %x n
    return [u32 $n]
}
proc checkpoint {phase} {
    foreach a {0xF8000108 0xF800010C 0xF8000170 0xF8000174 0xF8000178 0xF800017C 0xF8000180 0xF8000184 0xF8000188 0xF800018C 0xF8000240 0xF8000900} {
        say [format "PS_CHECKPOINT %s 0x%08X 0x%08X" $phase $a [rd $a]]
    }
}
proc restore {} {
    global saved cpu_saved modified stopped was_running
    # A configuration/status error can leave the selected target at the FPGA.
    if {$modified || $stopped} {targets -set -filter {name =~ "*Cortex-A9*#0"}}
    if {$modified} {
        wr 0xF8000008 0xDF0D
        # Approved terminal contract: assert four fabric resets, keep internal
        # PS/PL reset high bits deasserted; do not replay the POR high bits.
        set_checked 0xF8000240 0x0000000F
        mask_checked 0xF8000178 1 1
        mask_checked 0xF8000188 1 1
        foreach a {0xF8000170 0xF8000180 0xF8000900 0xF8000178 0xF8000188} {set_checked $a [dict get $saved $a]}
        foreach a {0xF8000170 0xF8000178 0xF8000180 0xF8000188 0xF8000900} {
            if {[rd $a]!=[dict get $saved $a]} {error "PS restore mismatch"}
        }
        if {[rd 0xF8000240]!=0xF} {error "PL isolated shutdown reset mismatch"}
        if {[dict get $saved 0xF800000C]&1} {wr 0xF8000004 0x767B}
        set modified 0
        say "PS_ISOLATED_SHUTDOWN_VERIFIED"
        say "PS_RESET_TERMINAL_CONTRACT 0xF8000240 0x0000000F POR_HIGH_BITS_NOT_RESTORED"
    }
    if {$stopped} {
        foreach name {pc sp lr cpsr} {
            set actual [cpu_reg $name]
            say [format "CPU_FINAL %s 0x%08X" $name $actual]
            if {$actual != [dict get $cpu_saved $name]} {error "CPU context mismatch"}
        }
        if {$was_running} {con;say "CPU0_RESUMED"}
        set stopped 0
    }
}

proc host_read_guard {a} {
    if {![string is wideinteger -strict $a] || ($a & 3)} {error "Invalid host read address"}
    set a [format 0x%08X $a]
    if {$a in {0x43C30008 0x43C3000C 0x43C30010 0x43C40008 0x43C4000C 0x43C50004 0x43C50008 0x43C50010 0x43C60004 0x43C60008}} {return}
    if {($a>=0x43C60020 && $a<=0x43C60038) || ($a>=0x43C60040 && $a<=0x43C60094)} {return}
    error "Host read outside ID/telemetry/diagnostic whitelist"
}
proc host_guard {a v} {

    if {![string is wideinteger -strict $a] || ![string is wideinteger -strict $v]} {error "Invalid host write"}
    if {$a==0x43C60040 && $v in {0 1}} {return}
    if {$a==0x43C6004C && $v>=0 && $v<4096} {return}
    if {$a==0x43C60088 && $v>=0 && $v<=0xffffffff && !($v & 0x7f000000)} {
        set reg [expr {($v>>8)&65535}]
        if {($v & 0x80000000) ? (($v & 255)==0) : ($reg in {13568 13569 13570 13571 13578 13579})} {return}
    }
    error "Only small snapshot control/address; all motion/config/diagnostic writes denied"
}
proc stream_guard {a count} {
    if {$a!=0x43C60050 || ![string is integer -strict $count] || $count<1 || $count>256} {error "Invalid snapshot stream range"}
}
if {[lindex $argv 0] eq "--check-only"} {
    foreach pair {{0x43C30004 1} {0x43C40000 1} {0x43C50000 1} {0x43C60040 2} {0x43C6004C 4096} {0x43C6008C 1} {0xF8000240 0}} {
        if {![catch {host_guard {*}$pair}]} {error "Forbidden host write accepted"}
    }
    foreach a {0xF8000240 0 0x43C30004 0x43C60098 0x43C60190} {
        if {![catch {host_read_guard $a}]} {error "Forbidden host read accepted"}
    }
    foreach a {0x43C30008 0x43C60048 0x43C60050 0x43C60078 0x43C60084} {host_read_guard $a}
    host_guard 0x43C60040 0;host_guard 0x43C60040 1
    host_guard 0x43C6004C 0;host_guard 0x43C6004C 4095
    foreach pair {{0x43C60050 0} {0x43C60050 257} {0x43C60054 1}} {
        if {![catch {stream_guard {*}$pair}]} {error "Bad stream allowed"}
    }
    host_guard 0x43C60088 0x80350300;host_guard 0x43C60088 0x00350303
    foreach v {0x00380001 0x01350303 0x80350301 -1 0x100000000} {
        if {![catch {host_guard 0x43C60088 $v}]} {error "Forbidden sensor command accepted"}
    }
    stream_guard 0x43C60050 256
    say "OFFLINE_PHASE2_GUARDS_PASS_NO_HARDWARE"
    exit 0
}
if {[llength $argv]!=4 || [lindex $argv 0] ne "--run"} {error "Use --check-only or --run BIT XSA OUTDIR"}
set bit [file normalize [lindex $argv 1]]
set xsa [file normalize [lindex $argv 2]]
set outdir [file normalize [lindex $argv 3]]
if {![file isfile $bit] || ![file isfile $xsa] || ![file isdirectory $outdir]} {error "Missing inputs"}
if {[file exists [file join $outdir HARDWARE_RUN_BLOCKED.json]]} {error "This version is authorized for offline work only; no hardware entry"}
# This attempt may be executed only once; there is no automatic retry.
set once [open [file join $outdir HARDWARE_RUN_STARTED.txt] {WRONLY CREAT EXCL}]
puts $once "v0.2.5 operator-controlled continuous LED camera-only session, arm disconnected and D5 low";close $once
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "*Cortex-A9*#0"}
    say "TARGETS_BEFORE [targets]"
    if {[regexp {Cortex-A9 MPCore #0 \(Running\)} [targets]]} {set was_running 1;stop}
    set stopped 1
    foreach name {pc sp lr cpsr} {dict set cpu_saved $name [cpu_reg $name];say [format "CPU_BEFORE %s 0x%08X" $name [dict get $cpu_saved $name]]}
    if {[rd 0xF800025C]!=0 || [dict get $cpu_saved pc]<0xffff0000} {error "Require JTAG BootROM wait"}
    if {[rd 0xF8000108]!=0x1A008 || !([rd 0xF800010C]&4)} {error "Unexpected IO PLL; no PLL changes allowed"}
    foreach a {0xF800000C 0xF8000170 0xF8000178 0xF8000180 0xF8000188 0xF8000240 0xF8000900} {dict set saved $a [rd $a]}
    set f [open [file join $outdir saved_ps_pl.tcldata] w];puts $f [list set saved $saved];puts $f [list set cpu_saved $cpu_saved];close $f
    say "PS_SAVED $saved"
    checkpoint BEFORE_CONFIG
    set modified 1
    wr 0xF8000008 0xDF0D
    mask_checked 0xF8000240 15 15
    mask_checked 0xF8000900 15 0
    mask_checked 0xF8000178 1 1
    mask_checked 0xF8000188 1 1
    mask_checked 0xF8000170 0x03F03F30 0x00200D00
    mask_checked 0xF8000180 0x03F03F30 0x00100D00
    mask_checked 0xF8000178 1 0
    mask_checked 0xF8000188 1 0
    wr 0xF8000004 0x767B
    say "FCLK_TARGETS_PREPARED_BEFORE_BIT"
    checkpoint BEFORE_BIT
    targets -set -filter {name =~ "xc7z020"}
    fpga -file $bit
    say "PHASE2_ALTERNATIVE_BIT_PROGRAMMED"
    say "FPGA_CONFIG_STATUS_BEGIN"
    say [fpga -config-status]
    say "FPGA_CONFIG_STATUS_END"
    set fpga_state [fpga -state]
    say "FPGA_CONFIGURATION_STATE $fpga_state"
    if {$fpga_state ne "FPGA is configured"} {error "FPGA startup incomplete; no AXI access"}
    targets -set -filter {name =~ "*Cortex-A9*#0"}
    wr 0xF8000008 0xDF0D
    # Exact same-XSA post-config release, not merely clearing the four user resets.
    mask_checked 0xF8000900 0xF 0xF
    set_checked 0xF8000240 0
    wr 0xF8000004 0x767B
    after 100
    checkpoint BEFORE_FIRST_AXI
    loadhw -hw $xsa -mem-ranges [list {0x43C30000 0x43C30FFF} {0x43C40000 0x43C40FFF} {0x43C50000 0x43C50FFF} {0x43C60000 0x43C60FFF}]
    say "MATCHING_XSA_FOUR_PL_PAGES_LOADED"
    foreach {a expected} $ids {
        set actual [rd $a]
        say [format "AXI_ID 0x%08X 0x%08X EXPECTED 0x%08X" $a $actual $expected]
        if {$actual!=$expected} {error "Original project ID mismatch"}
    }
    say "ALL_FOUR_ABIS_AND_MODEL_ID_PASS"
    if {[rd 0x43C30008]&12} {error "D5 must stay low; physical permission must be absent"}
    say "JTAG_READY"
    while {[gets stdin line]>=0} {
        if {[llength $line]<2} {error "Malformed host request"}
        set seq [lindex $line 0];set op [lindex $line 1]
        say "JTAG_REQUEST $line"
        if {$op eq "CLOSE"} {say "JTAG_REPLY $seq OK CLOSED";break}
        if {[catch {
            switch -- $op {
                R {
                    if {[llength $line]!=4} {error "Bad read request"}
                    set a [lindex $line 2];set count [lindex $line 3]
                    if {![string is integer -strict $count] || $count<1 || $count>32} {error "Read count denied"}
                    for {set i 0} {$i<$count} {incr i} {host_read_guard [expr {$a+4*$i}]}
                    set data {}
                    for {set i 0} {$i<$count} {incr i} {lappend data [format 0x%08X [rd [expr {$a+4*$i}]]]}
                }
                S {
                    if {[llength $line]!=4} {error "Bad stream request"}
                    set a [lindex $line 2];set count [lindex $line 3]
                    stream_guard $a $count
                    if {[rd 0x43C60040]!=1 || !([rd 0x43C60044]&1)} {error "Snapshot ownership/ready absent"}
                    if {[rd 0x43C6004C]+$count>4096} {error "Snapshot would overrun"}
                    set data {}
                    for {set i 0} {$i<$count} {incr i} {lappend data [format 0x%08X [rd $a]]}
                }
                W {
                    if {[llength $line]!=4} {error "Bad write request"}
                    set a [lindex $line 2];set value [lindex $line 3]
                    host_guard $a $value;wr $a $value;set data WRITTEN
                }
                default {error "Unknown host command"}
            }
        } issue]} {
            say "JTAG_REPLY $seq ERROR [string map {\r { } \n { }} $issue]"
            error $issue
        } else {say "JTAG_REPLY $seq OK $data"}
    }
} problem]} {say "VERIFY_ERROR [string map {\r { } \n { }} $problem]";set code 2}
if {$bus_fault} {
    say "STOPPED_AFTER_BUS_FAULT_NO_FURTHER_REGISTER_ACCESS_OR_RETRY"
    say "RESTORE_NOT_ATTEMPTED_AFTER_BUS_FAULT_USER_POWER_CYCLE_REQUIRED"
} else {
    set restore_failed 0
    if {[catch {restore} problem]} {
        say "RESTORE_ERROR [string map {\r { } \n { }} $problem]"
        set code 3
        set restore_failed 1
        if {$bus_fault} {
            say "STOPPED_DURING_RESTORE_BUS_FAULT_NO_FURTHER_MEMORY_OR_TARGET_QUERY"
            say "RESTORE_INCOMPLETE_USER_POWER_CYCLE_REQUIRED"
        } else {
            say "STOPPED_AFTER_RESTORE_ERROR_NO_FURTHER_TARGET_QUERY"
        }
    } else {say "RESTORE_COMPLETE"}
    if {!$bus_fault && !$restore_failed} {catch {say "TARGETS_FINAL [targets]"}}
}
catch {disconnect}
say "VERIFY_EXIT $code"
exit $code
