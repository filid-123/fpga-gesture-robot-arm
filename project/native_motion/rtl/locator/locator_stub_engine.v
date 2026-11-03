// ============================================================================
// Deterministic Phase 2-L1 data-plane stub.
// Reads all 4096 input words, XOR-reduces them, then writes 1280 output words.
// It verifies frame-buffer wiring/ownership before the trained CNN exists.
// output[word] = input_xor ^ frame_id ^ word_index.
// ============================================================================
`timescale 1ns / 1ps

module locator_stub_engine #(
    parameter integer INPUT_WORDS  = 4096,
    parameter integer OUTPUT_WORDS = 1280
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire        input_buffer_id,
    input  wire        output_buffer_id,
    input  wire [31:0] frame_id,

    output reg         input_bram_en,
    output reg  [12:0] input_bram_addr,
    input  wire [31:0] input_bram_data,

    output reg         output_bram_we,
    output reg  [11:0] output_bram_addr,
    output reg  [31:0] output_bram_data,

    output reg         busy,
    output reg         done,
    output reg         input_release,
    output wire        stall
);

    localparam S_IDLE  = 2'd0;
    localparam S_READ  = 2'd1;
    localparam S_WRITE = 2'd2;
    localparam S_FLUSH = 2'd3;

    reg [1:0]  state;
    reg        input_buffer_latched;
    reg        output_buffer_latched;
    reg [31:0] frame_id_latched;
    reg [12:0] read_issue_count;
    reg [12:0] read_feed_count;
    reg [10:0] write_count;
    reg        read_valid_d;
    reg [31:0] checksum;
    reg [31:0] checksum_final;

    assign stall = 1'b0;

    always @(posedge clk) begin
        if (!rst_n) begin
            state                  <= S_IDLE;
            input_buffer_latched   <= 1'b0;
            output_buffer_latched  <= 1'b0;
            frame_id_latched       <= 32'd0;
            read_issue_count       <= 13'd0;
            read_feed_count        <= 13'd0;
            write_count            <= 11'd0;
            read_valid_d           <= 1'b0;
            checksum               <= 32'd0;
            checksum_final         <= 32'd0;
            input_bram_en          <= 1'b0;
            input_bram_addr        <= 13'd0;
            output_bram_we         <= 1'b0;
            output_bram_addr       <= 12'd0;
            output_bram_data       <= 32'd0;
            busy                   <= 1'b0;
            done                   <= 1'b0;
            input_release          <= 1'b0;
        end else begin
            input_bram_en <= 1'b0;
            output_bram_we <= 1'b0;
            done <= 1'b0;
            input_release <= 1'b0;

            case (state)
                S_IDLE: begin
                    busy         <= 1'b0;
                    read_valid_d <= 1'b0;
                    if (start) begin
                        input_buffer_latched  <= input_buffer_id;
                        output_buffer_latched <= output_buffer_id;
                        frame_id_latched      <= frame_id;
                        read_issue_count      <= 13'd0;
                        read_feed_count       <= 13'd0;
                        checksum              <= 32'd0;
                        busy                  <= 1'b1;
                        state                 <= S_READ;
                    end
                end

                S_READ: begin
                    read_valid_d <= input_bram_en;
                    if (read_issue_count < INPUT_WORDS) begin
                        input_bram_en   <= 1'b1;
                        input_bram_addr <= {input_buffer_latched, read_issue_count[11:0]};
                        read_issue_count <= read_issue_count + 13'd1;
                    end

                    if (read_valid_d) begin
                        checksum        <= checksum ^ input_bram_data;
                        read_feed_count <= read_feed_count + 13'd1;
                        if ((read_feed_count + 13'd1) == INPUT_WORDS) begin
                            checksum_final <= checksum ^ input_bram_data;
                            input_release  <= 1'b1;
                            write_count    <= 11'd0;
                            state          <= S_WRITE;
                        end
                    end
                end

                S_WRITE: begin
                    output_bram_we   <= 1'b1;
                    output_bram_addr <= {output_buffer_latched, write_count};
                    output_bram_data <= checksum_final ^ frame_id_latched ^
                                        {21'd0, write_count};
                    if ((write_count + 11'd1) == OUTPUT_WORDS) begin
                        state <= S_FLUSH;
                    end else begin
                        write_count <= write_count + 11'd1;
                    end
                end

                S_FLUSH: begin
                    // The external synchronous BRAM commits the final write on
                    // this edge; publish done only after that edge.
                    busy  <= 1'b0;
                    done  <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
