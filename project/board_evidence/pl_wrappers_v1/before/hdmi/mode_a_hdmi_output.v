// Passive HDMI OUT branch, isolated from inference and motion control.
`timescale 1ns/1ps
module mode_a_hdmi_output #(parameter integer HD_PREVIEW=0,parameter FONT_FILE="mode_a_font.mem")(
 input wire sys_clk,sys_rst_n,pixel_clk,pixel_clk_5x,pixel_rst_n,
 input wire camera_we,input wire [13:0] camera_word_addr,input wire [31:0] camera_wdata,
 input wire camera_frame_published,input wire [31:0] camera_latest_frame_id,
 input wire result_valid,input wire [31:0] result_frame_id,input wire result_detected,
 input wire [8:0] box_x0,box_y0,box_x1,box_y1,
 input wire locator_fresh,gesture_valid,input wire [2:0] gesture_class,
 input wire [31:0] stage_loc_cycles,stage_cls_cycles,vision_age,
 input wire [31:0] task_status,interaction,arm_status,arm_error,feedback_masks,feedback_age,motion_frames,
 output wire tmds_clk_p,tmds_clk_n,output wire [2:0] tmds_data_p,tmds_data_n);
 wire [10:0] physical_x;wire [9:0] physical_y,x,y;wire active,hs,vs,start,pa,ph,pv,ps;wire[7:0]source_x,source_y;
 video_timing_720p timing(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.x(physical_x),.y(physical_y),.active_video(pa),.hsync(ph),.vsync(pv),.frame_start(ps));
 mode_a_720p_canvas canvas(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.physical_x(physical_x),.physical_y(physical_y),.logical_x(x),.logical_y(y),
  .source_x(source_x),.source_y(source_y),.active_in(pa),.hsync_in(ph),.vsync_in(pv),.start_in(ps),.active_out(active),.hsync_out(hs),.vsync_out(vs),.start_out(start));
 wire [13:0] addr;wire [31:0] data,display_id;
 wire valid,det;wire [8:0] x0,y0,x1,y1;
 mode_a_framebuffer #(.FRAME_WORDS(HD_PREVIEW!=0?12288:4096)) frame(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.camera_we(camera_we),.camera_word_addr(camera_word_addr),.camera_wdata(camera_wdata),
  .camera_frame_published(camera_frame_published),.camera_latest_frame_id(camera_latest_frame_id),.result_valid(result_valid),.result_frame_id(result_frame_id),.result_detected(result_detected),
  .box_x0(box_x0),.box_y0(box_y0),.box_x1(box_x1),.box_y1(box_y1),
  .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),.frame_start(start),.read_addr(addr),.read_data(data),
  .display_valid(valid),.display_detected(det),.x0(x0),.y0(y0),.x1(x1),.y1(y1),.display_frame_id(display_id));
 wire feedback_live=arm_status[6] && !arm_status[4] && arm_error==0 && feedback_masks[5:0]==63 && feedback_age[15:0]<=500;
 // Current task command is distinct from a physical per-command acknowledgement.
 wire[7:0]metric_loc,metric_cls;
 wire[7:0]metric_age=(vision_age>255)?255:vision_age;
 cycles_to_ms8 loc_units(sys_clk,sys_rst_n,stage_loc_cycles,metric_loc);
 cycles_to_ms8 cls_units(sys_clk,sys_rst_n,stage_cls_cycles,metric_cls);
 wire [93:0] source_ui={metric_loc,metric_cls,metric_age,locator_fresh,task_status,interaction,gesture_class,gesture_valid,feedback_live};
 wire [93:0] ui;
 mode_a_display_cdc #(.WIDTH(94)) status_cdc(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.source_data(source_ui),
  .pixel_clk(pixel_clk),.pixel_rst_n(pixel_rst_n),.frame_start(start),.display_data(ui));
 wire [7:0] r,g,b;wire de,rhs,rvs;
 mode_a_renderer #(.HD_PREVIEW(HD_PREVIEW),.PREMAPPED_SOURCE(HD_PREVIEW),.FONT_FILE(FONT_FILE)) renderer(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.timing_x(x),.timing_y(y),.timing_active(active),.timing_hsync(hs),.timing_vsync(vs),
  .mapped_source_x(source_x),.mapped_source_y(source_y),
  .frame_word_addr(addr),.frame_word_data(data),.display_valid(valid),.display_detected(det),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
  .metric_loc(ui[93:86]),.metric_cls(ui[85:78]),.metric_age(ui[77:70]),
  .locator_fresh(ui[69]),.task_status(ui[68:37]),.interaction(ui[36:5]),.gesture(ui[4:2]),.gesture_valid(ui[1]),.feedback_online(ui[0]),
  .red(r),.green(g),.blue(b),.data_enable(de),.hsync(rhs),.vsync(rvs));
 wire [9:0] tb,tg,tr;
 tmds_encoder eb(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(b),.data_enable(de),.control_0(rhs),.control_1(rvs),.tmds_word(tb));
 tmds_encoder eg(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(g),.data_enable(de),.control_0(1'b0),.control_1(1'b0),.tmds_word(tg));
 tmds_encoder er(.pixel_clk(pixel_clk),.rst_n(pixel_rst_n),.video_data(r),.data_enable(de),.control_0(1'b0),.control_1(1'b0),.tmds_word(tr));
 tmds_serializer_7series serializer(.pixel_clk(pixel_clk),.pixel_clk_5x(pixel_clk_5x),.rst_n(pixel_rst_n),.tmds_blue(tb),.tmds_green(tg),.tmds_red(tr),
  .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),.tmds_data_p(tmds_data_p),.tmds_data_n(tmds_data_n));
endmodule
