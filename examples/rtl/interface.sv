/**
 * @brief Simple clocked request/response interface.
 * @port clk Clock for the interface.
 */
interface handshake_if(input logic clk);
    logic request;
    logic acknowledge;
endinterface

/**
 * @brief Example constants used by the design.
 * @localparam RESET_VALUE Reset value used by example units.
 */
package example_pkg;
    localparam int RESET_VALUE = 0;
endpackage
