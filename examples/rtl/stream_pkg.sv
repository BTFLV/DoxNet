/**
 * @file
 * @brief Types and helpers shared by the streaming blocks.
 * @author Philip Mohr
 */

/**
 * @brief Common definitions for the byte stream datapath.
 *
 * Everything that crosses a module boundary in the example design is
 * declared here so that producers and consumers agree on the encoding.
 *
 * @localparam BYTE_W Width of one payload byte.
 * @since 1.0
 */
package stream_pkg;
  localparam int BYTE_W = 8;

  /// Line state of the UART transmitter.
  typedef enum logic [1:0] {
    TX_IDLE,
    TX_START,
    TX_DATA,
    TX_STOP
  } tx_state_e;

  /// One beat on a byte stream.
  typedef struct packed {
    logic [BYTE_W-1:0] data;  ///< Payload byte
    logic              last;  ///< Marks the final byte of a frame
  } beat_t;

  /**
   * @brief Number of clock cycles per UART bit, rounded to nearest.
   */
  function automatic int unsigned clocks_per_bit(int unsigned clk_hz, int unsigned baud);
    return (clk_hz + baud / 2) / baud;
  endfunction
endpackage
