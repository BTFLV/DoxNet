# Diagnostics

Diagnostics are printed as `file:line: CODE: message`, listed in the HTML and Markdown output and
included in the JSON report.

Errors mean DoxNet could not read the input reliably. They always stop the run with exit code 1 before
any output is written, because a half-parsed header would produce a wrong interface table. Warnings
point at documentation problems. They are reported but only fail the run with `--fail-on-warnings`.
Individual warning codes can be suppressed with `--disable` or the `disable` config key; errors cannot.

## HDL

| Code | Severity | Meaning |
|---|---|---|
| `HDL001` | error | A unit header could not be read: unbalanced parentheses, a missing `;` after the header, or a missing `endmodule`/`endinterface`/... |
| `HDL002` | warning | A unit name is defined more than once. The first definition is used for links and the hierarchy. |

## Preprocessor

| Code | Severity | Meaning |
|---|---|---|
| `PP001` | error | `` `else ``, `` `elsif `` or `` `endif `` without a matching `` `ifdef ``, or an `` `ifdef `` that is never closed |
| `PP002` | warning | An `` `include `` file was not found, could not be read, or includes itself |
| `PP003` | error | `` `ifdef ``/`` `ifndef ``/`` `elsif `` without a macro name or with an unreadable expression |

A missing include usually means an `--incdir` is missing. Since includes are only read for macro
definitions, the run continues, but `` `ifdef `` decisions that depend on that file may be wrong.

## Documentation

| Code | Severity | Meaning |
|---|---|---|
| `DOC001` | warning | A tag names a port, parameter, modport or instance that does not exist |
| `DOC002` | warning | `@input`, `@output`, `@inout` or `@param[in]` disagrees with the declared direction |
| `DOC003` | warning | The same entity is documented twice, e.g. by a tag and by a member comment |
| `DOC004` | warning | A comment with tags is not attached to any unit or declaration |
| `DOC005` | warning | Unknown tag, often a typo such as `@ouptut` |
| `DOC006` | warning | A tag such as `@port clk` has no description |

`DOC001` is the most useful one in practice: it catches comments that still describe a port that was
renamed or removed.

`DOC004` usually means there is code between the comment and the unit it was meant for:

```systemverilog
/** @brief Arbiter */
`timescale 1ns/1ps      // fine: directives and comments may come in between
import arb_pkg::*;      // code: the comment is no longer attached
module arbiter ...
```

## GitHub annotations

With `--diagnostics-format github`, diagnostics are printed as
[workflow commands](https://docs.github.com/actions/reference/workflow-commands-for-github-actions),
which show up as annotations on the affected lines of a pull request. File paths in annotations are
relative to the working directory, so run DoxNet from the repository root.
