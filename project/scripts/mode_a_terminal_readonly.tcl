# Attach to an already configured design. No reset, stop, program or write.
proc read_word {addr} {
    set values [mrd -address-space PA -value -size w $addr 1]
    if {[llength $values]!=1 || ![string is wideinteger -strict [lindex $values 0]]} {
        error {invalid memory read}
    }
    return [format 0x%08x [expr {[lindex $values 0] & 0xffffffff}]]
}
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "*Cortex-A9*#0"}
} err]} {puts "READONLY_ERROR $err";exit 2}
set addresses {}
foreach {base offsets} {
    0x43c30000 {0x8 0xc 0x10 0x200 0x204 0x208 0x20c 0x210 0x214 0x218 0x21c 0x300 0x304 0x308 0x30c}
    0x43c40000 {4 8 12 0x200 0x204 0x208 0x20c 0x210 0x214}
    0x43c50000 {4 8 12 0x10 0x1c 0x20 0x240 0x244 0x248 0x24c 0x25c}
    0x43c60000 {4 8 0x28 0x2c 0x38 0x5c 0x60 0x68 0x6c 0x70 0x78 0x80 0x84}
} {
    foreach offset $offsets {lappend addresses [expr {$base+$offset}]}
}
puts MODE_A_READONLY_READY
flush stdout
while {[gets stdin request] >= 0} {
    if {$request eq {Q}} {break}
    if {$request ne {S}} {puts {READONLY_ERROR unsupported request};flush stdout;continue}
    if {[catch {
        set values {}
        foreach addr $addresses {lappend values [read_word $addr]}
        puts "REGISTERS [join $values { }]"
        flush stdout
    } err]} {puts "READONLY_ERROR $err";flush stdout;break}
}
disconnect
exit 0
