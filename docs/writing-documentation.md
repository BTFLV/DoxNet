# Writing documentation comments

DoxNet reads Doxygen-style comments. The HDL declarations themselves supply names, directions, types,
widths and default values, so comments only need to say what things are for.

## Comment forms

| Form | Documents |
|---|---|
| `/** ... */`, `/*! ... */` | The declaration that follows |
| A run of `///` or `//!` lines | The declaration that follows |
| `///< ...`, `//!< ...`, `/**< ... */`, `/*!< ... */` | The declaration before it |
| Ordinary `// ...` after a port or parameter | Its own line's declaration, only with `--plain-comments` |

A leading comment must be directly in front of the declaration. Ordinary comments, attributes and
compiler directives such as `` `timescale `` may sit in between; code may not. A comment separated from
its unit by code is reported as `DOC004` instead of being attached to something else.

## Design units

Modules, macromodules, interfaces, packages, programs and UDPs (`primitive`) are recognized.

```systemverilog
/**
 * @brief Single-clock FIFO with registered outputs.
 *
 * Write and read may happen in the same cycle. Writing while `full` or
 * reading while `empty` is ignored.
 *
 * @note DEPTH must be a power of two.
 * @author Jane Doe
 * @version 1.2
 */
module sync_fifo #(
  parameter int WIDTH = 8,   ///< Data width in bits
  parameter int DEPTH = 16   ///< Number of entries
) (
  input  logic             clk,      ///< Clock
  input  logic             rst_n,    ///< Asynchronous reset, active low
  input  logic [WIDTH-1:0] wr_data,  ///< Data to push
  output logic             full      ///< No free entry left
);
```

The first paragraph becomes the brief description when there is no `@brief`. Everything else that is
not a tag is the detailed description. Descriptions are Markdown: lists, emphasis, `code` and fenced code
blocks work in the HTML output. Raw HTML is shown as text, never interpreted.

A tag's text runs until the next tag or the next blank line, so long descriptions can wrap:

```systemverilog
/**
 * @port irq Level-sensitive interrupt. Stays high until the
 *       status register is read.
 */
```

## Tag reference

Tags can be written with `@` or with a backslash (`\brief`).

### Unit description

| Tag | Meaning |
|---|---|
| `@brief`, `@short` | One-line summary |
| `@details` | Starts a description paragraph (optional, untagged text works too) |
| `@deprecated [text]` | Marks the unit as deprecated |
| `@note`, `@remark` | Highlighted note |
| `@warning`, `@attention` | Highlighted warning |
| `@todo` | Open item |
| `@see`, `@sa` | Reference; a unit name becomes a link |
| `@author`, `@version`, `@since`, `@date`, `@copyright`, `@license` | Shown as metadata |
| `@file` | Marks a comment as describing the file instead of the next unit |

### Interface entries

These name a declaration and describe it. They are an alternative to member comments; use one or the
other for a given entity.

| Tag | Matches |
|---|---|
| `@port <name> <text>` | Any port |
| `@input`, `@output`, `@inout`, `@ref` `<name> <text>` | A port, and checks its direction (`DOC002`) |
| `@parameter <name> <text>` | A parameter that can be overridden |
| `@localparam <name> <text>` | A local parameter |
| `@param <name> <text>` | A parameter, a local parameter or, if no parameter has that name, a port |
| `@param[in]`, `@param[out]`, `@param[in,out]` | A port with the given direction |
| `@modport <name> <text>` | An interface modport |
| `@instance <name> <text>` | An instance inside the unit |

The name may be followed by `-` or `:` (`@port clk - System clock`).

Every entry is checked against the parsed declaration. A name that does not exist (`DOC001`), the
wrong direction (`DOC002`), a duplicate (`DOC003`) or an entry without text (`DOC006`) is reported.
Unknown tags such as a misspelled `@ouptut` are reported as `DOC005`.

## Members

Besides ports and parameters, these declarations in a unit body can carry a leading or trailing comment
and are listed in the output:

- `localparam` and body `parameter` declarations
- non-ANSI port declarations (`input [7:0] a;`)
- `typedef`, `function`, `task` and `class` declarations
- `modport` items
- module and interface instances

```systemverilog
/// Line state of the transmitter.
typedef enum logic [1:0] {IDLE, START, DATA, STOP} state_e;

/// Transmit buffer
sync_fifo #(.WIDTH(8)) u_fifo (.clk, .rst_n /* ... */);

localparam int unsigned DIVISOR = CLK_HZ / BAUD;  ///< Clock cycles per bit
```

In a module with a `#(...)` parameter port list, a body `parameter` is local by the language rules and
is listed under local parameters. Package parameters are always local.

## File comments

A comment containing `@file` describes the file. It is shown above the units of that file and is never
attached to the following unit, so the unit can have its own comment:

```systemverilog
/**
 * @file
 * @brief Types shared by the streaming blocks.
 */

/** @brief Common stream definitions. */
package stream_pkg;
```

## Plain comments

Many existing code bases describe ports with ordinary comments:

```verilog
input  wire       clk,    // 100 MHz system clock
output reg  [7:0] count   // Current count
```

`--plain-comments` (config: `"plain_comments": true`) uses such a comment as the description when it
is on the same line as the declared name. Comments on their own line are still ignored, so section
headers like `// --- clocks ---` do not end up in the tables. The option is off by default because it
would otherwise count every stray remark as documentation.

## What counts as documented

- A unit is documented when it has a comment with any content.
- A port or parameter is documented when its description is not empty.
- Local parameters, modports, instances and members are shown but do not affect coverage.

See [Configuration](configuration.md#quality-gates) for the thresholds.
