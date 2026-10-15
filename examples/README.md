# Example: buffered UART transmitter

A small but complete design that uses most of what DoxNet understands:

| File | Shows |
|---|---|
| `rtl/stream_pkg.sv` | `@file` comment, package with typedefs and a function |
| `rtl/stream_if.sv` | Interface with modports documented through tags |
| `rtl/sync_fifo.sv` | Trailing `///<` comments on parameters and ports, `@note`, metadata |
| `rtl/uart_tx.sv` | Tags in the unit comment, an interface port, `` `include `` of a macro header |
| `rtl/uart_top.sv` | Instances, `` `ifdef `` around a port, `@warning`, `@todo`, `@see` |

```bash
doxnet -c examples/doxnet.json -o build/example
doxnet -c examples/doxnet.json -o build/example-debug -D UART_DEBUG
```

The second command enables the debug port of `uart_top`. The config sets every coverage gate to 100 %
and fails on warnings, so it also serves as a regression test in CI.
