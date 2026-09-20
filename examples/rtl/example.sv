/**
 * @brief A simple example module.
 *
 * Demonstrates how to document a Verilog/SystemVerilog module using DoxNet.
 *
 * @parameter WIDTH Bit width of data bus.
 * @localparam DEPTH Internal FIFO depth.
 *
 * @input clk Clock signal.
 * @input rst_n Active-low reset.
 * @input enable Enable signal.
 * @inout data Data bus (bidirectional).
 *
 * @output ready Ready flag.
 */
module example #(parameter WIDTH = 8) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        enable,
  inout  wire [WIDTH-1:0] data,
  output wire        ready
);
  localparam DEPTH = 16;
  // ...
endmodule
