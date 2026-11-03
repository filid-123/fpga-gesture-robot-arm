# PC-only stubs; no XSDB hardware library is loaded.

set sim_events {}
set sim_lines {}
set sim_exit -1
set sim_running 1
set sim_target CPU0
set sim_faulted 0
set sim_after_fault_accesses 0
set sim_registers [dict create \
    0xF800000C 1 0xF8000108 0x1A008 0xF800010C 4 \
    0xF8000170 0x00101800 0xF8000174 0 0xF8000178 0 0xF800017C 0 \
    0xF8000180 0x00101800 0xF8000184 0 0xF8000188 0 0xF800018C 0 \
    0xF8000240 0x01F33F0F 0xF800025C 0 0xF8000900 0 \
    0x43C30008 0x20 0x43C30010 0x3101 0x43C4000C 0x3202 0x43C50010 0x3404 \
    0x43C60008 0x3505 0x43C60070 0x022267A9]
set sim_initial $sim_registers
rename puts original_puts
proc puts {args} {
    if {[llength $args]==1} {lappend ::sim_lines [lindex $args 0]} else {original_puts {*}$args}
}
proc exit {n} {set ::sim_exit $n}
proc connect {args} {lappend ::sim_events CONNECT}
proc disconnect {} {lappend ::sim_events DISCONNECT}
proc gets {channel name} {return -1}
proc targets {args} {
    if {[llength $args]} {
        set ::sim_target [expr {[string match *xc7z020* [lindex $args end]] ? "FPGA" : "CPU0"}]
        return
    }
    set state [expr {$::sim_running ? "Running" : "Stopped"}]
    return "2 ARM Cortex-A9 MPCore #0 ($state)\n3 ARM Cortex-A9 MPCore #1 (Running)\n4 xc7z020"
}
proc stop {} {set ::sim_running 0;lappend ::sim_events STOP_CPU0}
proc con {} {set ::sim_running 1;lappend ::sim_events RESUME_CPU0}
proc rrd {name} {
    if {$::sim_target ne "CPU0"} {error "CPU register access selected wrong target"}
    return "$name: [dict get {pc FFFFFF28 sp E5801000 lr FFFFFF20 cpsr 200001DF} $name]"
}
proc mrd {args} {
    if {$::sim_faulted} {incr ::sim_after_fault_accesses;error "Access after bus fault"}
    if {$::sim_target ne "CPU0"} {error "PA read selected wrong target"}
    set a [format 0x%08X [expr {[lindex $args end-1]}]]
    lappend ::sim_events [list READ $a]
    if {$::sim_case eq "first_id_timeout" && $a eq "0x43C30010"} {
        set ::sim_faulted 1
        error "Memory read error at 0x43C30010. Timeout waiting for the Instruction Complete bit"
    }
    if {$::sim_case eq "id_mismatch" && $a eq "0x43C30010"} {return 0x3102}
    if {$::sim_case eq "legacy_model_id" && $a eq "0x43C60070"} {return 0x0F350087}
    if {![dict exists $::sim_registers $a]} {error "Read outside expected register set"}
    return [dict get $::sim_registers $a]
}
proc mwr {args} {
    if {$::sim_faulted} {incr ::sim_after_fault_accesses;error "Access after bus fault"}
    if {$::sim_target ne "CPU0"} {error "PA write selected wrong target"}
    set a [format 0x%08X [expr {[lindex $args end-1]}]]
    set v [expr {[lindex $args end] & 0xffffffff}]
    if {$a ni {0xF8000004 0xF8000008 0xF8000170 0xF8000178 0xF8000180 0xF8000188 0xF8000240 0xF8000900}} {error "Forbidden write"}
    lappend ::sim_events [list WRITE $a $v]
    dict set ::sim_registers $a $v
}
proc fpga {args} {
    if {$::sim_target ne "FPGA"} {error "FPGA operation selected wrong target"}
    if {[lindex $args 0] eq "-file"} {
        foreach {a expected} {0xF8000170 0x00200D00 0xF8000180 0x00100D00 0xF8000178 0 0xF8000188 0 0xF8000900 0} {
            if {[dict get $::sim_registers $a]!=$expected} {error "Clocks/crossings were not prepared before BIT"}
        }
        if {([dict get $::sim_registers 0xF8000240]&15)!=15} {error "Fabric reset not asserted during BIT"}
        lappend ::sim_events BIT_DOWNLOAD
        return
    }
    if {[lindex $args 0] eq "-config-status"} {
        lappend ::sim_events FPGA_CONFIG_READ
        if {$::sim_case eq "configuration_status_error"} {error "Simulated status query error"}
        return "MOCK CONFIG STATUS: local simulator only"
    }
    if {[lindex $args 0] eq "-state"} {
        lappend ::sim_events FPGA_STATE_READ
        return [expr {$::sim_case eq "startup_incomplete" ? "FPGA is not configured" : "FPGA is configured"}]
    }
    error "Unapproved FPGA operation"
}
proc loadhw {args} {lappend ::sim_events MAP_FOUR_PAGES}

# Inject failures only after the simulated host CLOSE. These cases exercise
# the previously uncovered restore-internal error branch, not physical I/O.
set sim_close_seen 0
set sim_target_queries_after_fault 0
rename gets sim_old_gets
proc gets {channel name} {
    if {$::sim_close_seen} {return -1}
    upvar 1 $name line
    set line "1 CLOSE"
    set ::sim_close_seen 1
    lappend ::sim_events HOST_CLOSE
    return [string length $line]
}
rename targets sim_base_targets
proc targets {args} {
    if {$::sim_faulted} {
        incr ::sim_target_queries_after_fault
        error "Target operation after injected fault"
    }
    if {![llength $args]} {lappend ::sim_events TARGET_QUERY}
    return [sim_base_targets {*}$args]
}
proc sim_fail {description} {
    set ::sim_faulted 1
    lappend ::sim_events [list INJECTED_FAULT $description]
    error "Simulated cleanup bus fault: $description"
}
rename mrd sim_base_mrd
proc mrd {args} {
    set a [format 0x%08X [expr {[lindex $args end-1]}]]
    if {$::sim_close_seen && !$::sim_faulted} {
        if {$::sim_case eq "reset_readback_fault" && $a eq "0xF8000240"} {sim_fail RESET_READBACK}
        if {$::sim_case eq "isolation_readback_fault" && $a eq "0xF8000900"} {sim_fail ISOLATION_READBACK}
    }
    return [sim_base_mrd {*}$args]
}
rename mwr sim_base_mwr
proc mwr {args} {
    set a [format 0x%08X [expr {[lindex $args end-1]}]]
    if {$::sim_close_seen && !$::sim_faulted} {
        if {$::sim_case eq "reset_write_fault" && $a eq "0xF8000240"} {sim_fail RESET_WRITE}
        if {$::sim_case eq "clock_restore_write_fault" && $a eq "0xF8000170"} {sim_fail CLOCK_RESTORE_WRITE}
    }
    return [sim_base_mwr {*}$args]
}
rename rrd sim_base_rrd
proc rrd {name} {
    if {$::sim_close_seen && !$::sim_faulted && $::sim_case eq "cpu_read_fault"} {sim_fail CPU_READ}
    return [sim_base_rrd $name]
}
