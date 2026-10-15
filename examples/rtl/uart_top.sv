/**
 * @brief Buffered UART transmitter.
 *
 * Bytes written to the FIFO are sent over `txd` as soon as the transmitter
 * is free.
 *
 * ```
 * wr_* --> sync_fifo --> stream_if --> uart_tx --> txd
 * ```
 *
 * @warning `wr_en` while `full` is high drops the byte silently.
 * @todo Add a receive path.
 * @see uart_tx
 */
module uart_top #(
  parameter int unsigned CLK_HZ     = 50_000_000,  ///< System clock in Hz
  parameter int unsigned BAUD       = 115_200,     ///< UART line rate
  parameter int          FIFO_DEPTH = 32           ///< Transmit buffer entries
) (
  input  logic       clk,      ///< System clock
  input  logic       rst_n,    ///< Asynchronous reset, active low
  input  logic       wr_en,    ///< Queue `wr_data` for transmission
  input  logic [7:0] wr_data,  ///< Byte to queue
  output logic       full,     ///< Transmit buffer full
  output logic       txd       ///< Serial output
`ifdef UART_DEBUG
  ,
  output logic       busy      ///< Transmitter active (debug builds only)
`endif
);
  logic fifo_empty;
  logic tx_busy;

  stream_if tx_stream (.clk);

  /// Transmit buffer
  sync_fifo #(
    .WIDTH(8),
    .DEPTH(FIFO_DEPTH)
  ) u_fifo (
    .clk,
    .rst_n,
    .wr_en,
    .wr_data,
    .full,
    .rd_en  (tx_stream.valid && tx_stream.ready),
    .rd_data(tx_stream.beat.data),
    .empty  (fifo_empty)
  );

  assign tx_stream.valid     = !fifo_empty;
  assign tx_stream.beat.last = 1'b0;

  uart_tx #(
    .CLK_HZ(CLK_HZ),
    .BAUD  (BAUD)
  ) u_tx (
    .clk,
    .rst_n,
    .in  (tx_stream),
    .txd,
    .busy(tx_busy)
  );  ///< Serializer

`ifdef UART_DEBUG
  assign busy = tx_busy;
`endif
endmodule
