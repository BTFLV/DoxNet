/**
 * @brief Single-clock FIFO with registered outputs.
 *
 * Write and read may happen in the same cycle. Writing while `full` or
 * reading while `empty` is ignored.
 *
 * @note DEPTH must be a power of two.
 * @author Philip Mohr
 * @version 1.2
 */
module sync_fifo #(
  parameter int WIDTH = 8,   ///< Data width in bits
  parameter int DEPTH = 16   ///< Number of entries
) (
  input  logic             clk,      ///< Clock
  input  logic             rst_n,    ///< Asynchronous reset, active low
  input  logic             wr_en,    ///< Push `wr_data` this cycle
  input  logic [WIDTH-1:0] wr_data,  ///< Data to push
  output logic             full,     ///< No free entry left
  input  logic             rd_en,    ///< Pop one entry this cycle
  output logic [WIDTH-1:0] rd_data,  ///< Oldest entry
  output logic             empty     ///< No entry available
);
  localparam int AW = $clog2(DEPTH);  ///< Address width

  logic [WIDTH-1:0] mem [DEPTH];
  logic [AW:0]      wr_ptr, rd_ptr;

  assign full  = (wr_ptr[AW] != rd_ptr[AW]) && (wr_ptr[AW-1:0] == rd_ptr[AW-1:0]);
  assign empty = wr_ptr == rd_ptr;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      wr_ptr <= '0;
      rd_ptr <= '0;
    end else begin
      if (wr_en && !full) begin
        mem[wr_ptr[AW-1:0]] <= wr_data;
        wr_ptr <= wr_ptr + 1'b1;
      end
      if (rd_en && !empty) begin
        rd_ptr <= rd_ptr + 1'b1;
      end
    end
  end

  assign rd_data = mem[rd_ptr[AW-1:0]];
endmodule
