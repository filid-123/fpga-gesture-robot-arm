// ============================================================================
// Fixed Phase 2-L2 locator preprocessor:
//   640x480 Gray8 -> nearest-neighbor 128x96 -> zero pad to 128x128.
// The OpenCV INTER_NEAREST mapping is exact for this 5:1 integer reduction:
// dst(x,y) samples src(5*x,5*y), with 16 rows of padding above and below.
// Four pixels are packed little-endian into each 32-bit BRAM word.
// ============================================================================
`timescale 1ns / 1ps

module pl_letterbox_640x480 #(
    parameter integer SOURCE_WIDTH  = 640,
    parameter integer SOURCE_HEIGHT = 480,
    parameter integer DECIMATION    = 5,
    parameter integer PAD_TOP       = 16,
    parameter integer CONTENT_ROWS  = 96,
    parameter integer CYCLES_PER_MS = 100000
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        pixel_valid,
    output wire        pixel_ready,
    input  wire [7:0]  pixel_data,
    input  wire [9:0]  pixel_x,
    input  wire [9:0]  pixel_y,
    input  wire        pixel_sof,

    input  wire [1:0]  buffer_release,
    output reg  [1:0]  buffer_valid_mask,
    output reg  [31:0] buffer_frame_id_0,
    output reg  [31:0] buffer_frame_id_1,
    output reg         frame_published,
    output reg         latest_buffer_id,
    output reg  [31:0] latest_frame_id,

    output reg         mem_we,
    output reg  [12:0] mem_word_addr,
    output reg  [31:0] mem_wdata,

    output reg [31:0] buffer_timestamp_ms_0, buffer_timestamp_ms_1, now_ms,
    output reg  [31:0] frame_drop_count,
    output wire preview_accept_sof,output wire[31:0]preview_frame_id,
    output reg  [31:0] format_error_count
);

    localparam [2:0] ST_WAIT_SOF   = 3'd0;
    localparam [2:0] ST_TOP_PAD    = 3'd1;
    localparam [2:0] ST_ACTIVE     = 3'd2;
    localparam [2:0] ST_BOTTOM_PAD = 3'd3;
    localparam [2:0] ST_PUBLISH    = 3'd4;
    localparam [2:0] ST_DROP       = 3'd5;

    localparam integer WORDS_PER_ROW   = 128 / 4;
    localparam integer TOP_PAD_WORDS   = PAD_TOP * WORDS_PER_ROW;
    localparam integer CONTENT_WORDS   = CONTENT_ROWS * WORDS_PER_ROW;
    localparam integer BOTTOM_PAD_BASE = TOP_PAD_WORDS + CONTENT_WORDS;
    localparam integer BOTTOM_PAD_WORDS = (128 - PAD_TOP - CONTENT_ROWS) * WORDS_PER_ROW;

    reg [$clog2(CYCLES_PER_MS)-1:0] ms_div;
    reg [31:0] captured_ms;
    reg [2:0] state;
    reg       write_buffer_id;
    reg [9:0] pad_word_count;
    reg [1:0] pack_count;
    reg [31:0] pack_data;
    reg [31:0] next_frame_id;
    reg [31:0] current_frame_id;

    reg        pending_valid;
    reg [7:0]  pending_data;
    reg [9:0]  pending_x;
    reg [9:0]  pending_y;
    reg        pending_sof;

    wire [1:0] effective_valid = buffer_valid_mask & ~buffer_release;
    wire [1:0] free_mask = ~effective_valid;
    wire       have_free_buffer = |free_mask;
    wire       selected_free_buffer = free_mask[0] ? 1'b0 : 1'b1;

    assign preview_accept_sof=pixel_valid && pixel_ready && pixel_sof && have_free_buffer && (state==ST_WAIT_SOF || state==ST_DROP);
    assign preview_frame_id=next_frame_id;
    wire       active_valid = pending_valid || pixel_valid;
    wire [7:0] active_data  = pending_valid ? pending_data : pixel_data;
    wire [9:0] active_x     = pending_valid ? pending_x : pixel_x;
    wire [9:0] active_y     = pending_valid ? pending_y : pixel_y;
    wire       active_sof   = pending_valid ? pending_sof : pixel_sof;

    wire selected_pixel =
        (active_x < SOURCE_WIDTH) &&
        (active_y < SOURCE_HEIGHT) &&
        ((active_x % DECIMATION) == 0) &&
        ((active_y % DECIMATION) == 0);

    wire last_selected_pixel =
        (active_x == (SOURCE_WIDTH - DECIMATION)) &&
        (active_y == (SOURCE_HEIGHT - DECIMATION));

    assign pixel_ready =
        (state == ST_WAIT_SOF) ||
        (state == ST_DROP) ||
        ((state == ST_ACTIVE) && !pending_valid);

    always @(posedge clk) begin
        if (!rst_n) begin
            now_ms<=0;ms_div<=0;captured_ms<=0;
            buffer_timestamp_ms_0<=0;buffer_timestamp_ms_1<=0;
            state                <= ST_WAIT_SOF;
            write_buffer_id      <= 1'b0;
            pad_word_count       <= 10'd0;
            pack_count           <= 2'd0;
            pack_data            <= 32'd0;
            next_frame_id        <= 32'd0;
            current_frame_id     <= 32'd0;
            pending_valid        <= 1'b0;
            pending_data         <= 8'd0;
            pending_x            <= 10'd0;
            pending_y            <= 10'd0;
            pending_sof          <= 1'b0;
            buffer_valid_mask    <= 2'b00;
            buffer_frame_id_0    <= 32'd0;
            buffer_frame_id_1    <= 32'd0;
            frame_published      <= 1'b0;
            latest_buffer_id     <= 1'b0;
            latest_frame_id      <= 32'd0;
            mem_we               <= 1'b0;
            mem_word_addr        <= 13'd0;
            mem_wdata            <= 32'd0;
            frame_drop_count     <= 32'd0;
            format_error_count   <= 32'd0;
        end else begin
            if(ms_div==CYCLES_PER_MS-1)begin ms_div<=0;now_ms<=now_ms+1;end
            else ms_div<=ms_div+1;
            mem_we            <= 1'b0;
            frame_published   <= 1'b0;
            buffer_valid_mask <= effective_valid;

            case (state)
                ST_WAIT_SOF: begin
                    pending_valid <= 1'b0;
                    pack_count    <= 2'd0;
                    pack_data     <= 32'd0;
                    if (pixel_valid && pixel_sof) begin
                        if (have_free_buffer) begin
                            captured_ms<=now_ms;
                            write_buffer_id  <= selected_free_buffer;
                            current_frame_id <= next_frame_id;
                            next_frame_id    <= next_frame_id + 32'd1;
                            pending_valid    <= 1'b1;
                            pending_data     <= pixel_data;
                            pending_x        <= pixel_x;
                            pending_y        <= pixel_y;
                            pending_sof      <= pixel_sof;
                            pad_word_count   <= 10'd0;
                            state            <= ST_TOP_PAD;
                        end else begin
                            frame_drop_count <= frame_drop_count + 32'd1;
                            state            <= ST_DROP;
                        end
                    end
                end

                ST_TOP_PAD: begin
                    mem_we        <= 1'b1;
                    mem_word_addr <= {write_buffer_id, 12'd0} + pad_word_count;
                    mem_wdata     <= 32'd0;
                    if (pad_word_count == (TOP_PAD_WORDS - 1)) begin
                        pad_word_count <= 10'd0;
                        state          <= ST_ACTIVE;
                    end else begin
                        pad_word_count <= pad_word_count + 10'd1;
                    end
                end

                ST_ACTIVE: begin
                    if (active_valid) begin
                        if (active_sof && !pending_valid &&
                            ((active_x != 0) || (active_y != 0) || (pack_count != 0))) begin
                            captured_ms<=now_ms;
                            // A new frame arrived before the expected final VGA sample.
                            format_error_count <= format_error_count + 32'd1;
                            current_frame_id   <= next_frame_id;
                            next_frame_id      <= next_frame_id + 32'd1;
                            pending_valid      <= 1'b1;
                            pending_data       <= active_data;
                            pending_x          <= active_x;
                            pending_y          <= active_y;
                            pending_sof        <= 1'b1;
                            pad_word_count     <= 10'd0;
                            pack_count         <= 2'd0;
                            pack_data          <= 32'd0;
                            state              <= ST_TOP_PAD;
                        end else begin
                            if (pending_valid)
                                pending_valid <= 1'b0;

                            if (selected_pixel) begin
                                case (pack_count)
                                    2'd0: pack_data[7:0]   <= active_data;
                                    2'd1: pack_data[15:8]  <= active_data;
                                    2'd2: pack_data[23:16] <= active_data;
                                    default: pack_data[31:24] <= active_data;
                                endcase

                                if (pack_count == 2'd3) begin
                                    mem_we <= 1'b1;
                                    mem_word_addr <= {write_buffer_id, 12'd0} +
                                        TOP_PAD_WORDS +
                                        ((active_y / DECIMATION) * WORDS_PER_ROW) +
                                        ((active_x / DECIMATION) >> 2);
                                    mem_wdata <= {active_data, pack_data[23:0]};
                                    pack_count <= 2'd0;
                                    if (last_selected_pixel) begin
                                        pad_word_count <= 10'd0;
                                        state          <= ST_BOTTOM_PAD;
                                    end
                                end else begin
                                    pack_count <= pack_count + 2'd1;
                                end
                            end
                        end
                    end
                end

                ST_BOTTOM_PAD: begin
                    mem_we        <= 1'b1;
                    mem_word_addr <= {write_buffer_id, 12'd0} +
                                     BOTTOM_PAD_BASE + pad_word_count;
                    mem_wdata     <= 32'd0;
                    if (pad_word_count == (BOTTOM_PAD_WORDS - 1)) begin
                        pad_word_count <= 10'd0;
                        state          <= ST_PUBLISH;
                    end else begin
                        pad_word_count <= pad_word_count + 10'd1;
                    end
                end

                ST_PUBLISH: begin
                    if(write_buffer_id)buffer_timestamp_ms_1<=captured_ms;
                    else buffer_timestamp_ms_0<=captured_ms;
                    buffer_valid_mask[write_buffer_id] <= 1'b1;
                    if (write_buffer_id)
                        buffer_frame_id_1 <= current_frame_id;
                    else
                        buffer_frame_id_0 <= current_frame_id;
                    latest_buffer_id <= write_buffer_id;
                    latest_frame_id  <= current_frame_id;
                    frame_published  <= 1'b1;
                    state            <= ST_WAIT_SOF;
                end

                ST_DROP: begin
                    if (pixel_valid && pixel_sof) begin
                        if (have_free_buffer) begin
                            captured_ms<=now_ms;
                            write_buffer_id  <= selected_free_buffer;
                            current_frame_id <= next_frame_id;
                            next_frame_id    <= next_frame_id + 32'd1;
                            pending_valid    <= 1'b1;
                            pending_data     <= pixel_data;
                            pending_x        <= pixel_x;
                            pending_y        <= pixel_y;
                            pending_sof      <= pixel_sof;
                            pad_word_count   <= 10'd0;
                            pack_count       <= 2'd0;
                            pack_data        <= 32'd0;
                            state            <= ST_TOP_PAD;
                        end else begin
                            frame_drop_count <= frame_drop_count + 32'd1;
                        end
                    end
                end

                default: state <= ST_WAIT_SOF;
            endcase
        end
    end

endmodule
