/**
 * @brief Ready/valid byte stream.
 *
 * A transfer happens on every rising clock edge where both `valid` and
 * `ready` are high. The producer must hold `data` stable while `valid` is
 * asserted and `ready` is low.
 *
 * @modport source Producer side.
 * @modport sink Consumer side.
 */
interface stream_if
  import stream_pkg::*;
(
  input logic clk  ///< Interface clock
);
  beat_t beat;
  logic  valid;
  logic  ready;

  modport source(output beat, output valid, input ready);
  modport sink(input beat, input valid, output ready);
endinterface
