// ============================================================================
// Phase 2-L1 locator interrupt level synchronizer.
//
// locator_top holds irq_level high until CLEAR_IRQ, so a two-flop level
// synchronizer is sufficient when crossing from the 100 MHz locator domain to
// the 50 MHz PS/AXI Interrupt Controller domain. Pulse-only sources must not be
// connected to this module.
// ============================================================================
`timescale 1ns / 1ps

module locator_irq_sync (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 dst_clk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME dst_clk, ASSOCIATED_RESET dst_resetn, FREQ_HZ 50000000" *)
    input  wire dst_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 dst_resetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME dst_resetn, POLARITY ACTIVE_LOW" *)
    input  wire dst_resetn,
    input  wire async_irq_level,
    output wire synced_irq_level
);

    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg sync_ff1;
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *) reg sync_ff2;

    always @(posedge dst_clk) begin
        if (!dst_resetn) begin
            sync_ff1 <= 1'b0;
            sync_ff2 <= 1'b0;
        end else begin
            sync_ff1 <= async_irq_level;
            sync_ff2 <= sync_ff1;
        end
    end

    assign synced_irq_level = sync_ff2;

endmodule
