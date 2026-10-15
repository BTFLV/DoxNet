`include "defs.svh"

/**
 * @brief 8N1 UART transmitter.
 *
 * Takes bytes from a stream interface and shifts them out LSB first with one
 * start and one stop bit.
 *
 * @parameter CLK_HZ Frequency of `clk` in Hz.
 * @parameter BAUD Line rate in bit/s.
 * @port clk Clock.
 * @port rst_n Asynchronous reset, active low.
 * @port in Bytes to send.
 * @port txd Serial output, idles high.
 * @port busy High while a frame is on the line.
 */
module uart_tx
  import stream_pkg::*;
#(
  parameter int unsigned CLK_HZ = 50_000_000,
  parameter int unsigned BAUD   = `UART_DEFAULT_BAUD
) (
  input  logic     clk,
  input  logic     rst_n,
  stream_if.sink   in,
  output logic     txd,
  output logic     busy
);
  localparam int unsigned DIVISOR = clocks_per_bit(CLK_HZ, BAUD);  ///< Clock cycles per bit

  tx_state_e                      state;
  logic [$clog2(DIVISOR)-1:0]     count;
  logic [2:0]                     bit_idx;
  logic [BYTE_W-1:0]              shift;

  assign in.ready = state == TX_IDLE;
  assign busy     = state != TX_IDLE;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= TX_IDLE;
      txd   <= 1'b1;
    end else begin
      unique case (state)
        TX_IDLE: if (in.valid) begin
          shift <= in.beat.data;
          state <= TX_START;
          count <= '0;
          txd   <= 1'b0;
        end
        TX_START, TX_DATA, TX_STOP: begin
          count <= count + 1'b1;
          if (count == DIVISOR - 1) begin
            count <= '0;
            if (state == TX_STOP) begin
              state <= TX_IDLE;
            end else if (state == TX_DATA && bit_idx == 3'd7) begin
              state <= TX_STOP;
              txd   <= 1'b1;
            end else begin
              state   <= TX_DATA;
              txd     <= shift[0];
              shift   <= shift >> 1;
              bit_idx <= (state == TX_START) ? 3'd0 : bit_idx + 1'b1;
            end
          end
        end
      endcase
    end
  end
endmodule
