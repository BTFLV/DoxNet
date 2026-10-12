/**
 * @brief Configurable example datapath
 *
 * Demonstrates HDL-derived port/parameter tables with Doxygen-style descriptions.
 *
 * @parameter WIDTH Width of the data bus.
 * @input clk System clock.
 * @input rst_n Active-low reset.
 * @input enable Enables the output.
 * @inout data Bidirectional data bus.
 * @output ready Output valid indicator.
 * @localparam DEPTH Internal FIFO depth.
 */
module example #(parameter int WIDTH = 8) (
  input logic             clk,
  input logic             rst_n,
  input logic             enable,
  inout wire [WIDTH-1:0] data,
  output logic            ready
);
  localparam int DEPTH = 16;
endmodule
