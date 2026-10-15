# Inputs and preprocessing

## Choosing files

There are three ways to tell DoxNet what to read. They can be combined: explicit files from the config
and the filelist are used together, and `--input` then only sets the root for display names.

| Source | Order | Display names |
|---|---|---|
| `--input DIR` | Sorted by path | Relative to `DIR` |
| `files` in the config | As listed | Relative to `input`, or to the config directory |
| `--filelist FILE` | As listed | Relative to `input`, or to the filelist directory |

Order matters for two things: the order of the generated document, and macro definitions, which
carry over from one file to the next (see below).

When scanning a directory, symbolic links that point outside of it are rejected. `exclude` globs are
matched against the display name, e.g. `--exclude 'sim/*' --exclude '*_tb.sv'`.

## Filelists

DoxNet understands the common subset of simulator filelists:

```text
# comments start with # or //
+incdir+include+../common/include
+define+SYNTHESIS+BUS_WIDTH=64
$PROJECT_ROOT/rtl/top.sv
${IP_ROOT}/fifo/fifo.sv     // trailing comments are fine
-f ../common/common.f
```

- One or more source files per line.
- `-f` and `-F` include another filelist. Both are resolved relative to the filelist that contains
  them.
- `+incdir+` and `+define+` accept several `+`-separated values.
- `$VAR`, `${VAR}` and `$(VAR)` are replaced from the environment. An unset variable is an error.
- Relative paths are relative to the filelist.

Options DoxNet cannot honor, such as `-y`, `-v` or `+libext+`, are rejected with an error instead of
being ignored.

## Conditional compilation

DoxNet evaluates `` `ifdef ``, `` `ifndef ``, `` `elsif ``, `` `else `` and `` `endif ``. Code in an
inactive branch does not produce design units, ports or documentation, and does not count towards
coverage. This is what a reader of the generated documentation expects, and it keeps coverage honest
for designs with optional features.

```bash
doxnet -i rtl -o docs -D SYNTHESIS -D BUS_WIDTH=64
```

The macro set for each file is made of:

1. `SYSTEMVERILOG`, which is always defined;
2. `defines` from the config and `-D` on the command line;
3. `+define+` from filelists (the command line and config win on conflicts);
4. `` `define `` and `` `undef `` in the sources, in file order.

All inputs form one compilation unit, as with most simulators: a macro defined in `defs.svh` is visible
in every file processed after it. IEEE 1800-2023 conditional expressions like
`` `ifdef (A && !B) `` are supported.

`` `include `` is followed only to pick up macro definitions; the content of an included file is not
parsed as part of the including file. Include files are searched next to the including file and then
in `include_dirs`. Header files that contain design units should be inputs in their own right; the
directory scan picks up `.vh` and `.svh` automatically.

Macros are not expanded. A port declared as ``input logic [`WIDTH-1:0] data`` shows its type exactly
like that.

Use `--no-preprocess` to parse every branch. In that mode, code like the following yields two
definitions of `fifo` and an `HDL002` warning:

```systemverilog
`ifdef ASIC
module fifo ...;   // macro-based memory
`else
module fifo ...;   // inferred memory
`endif
```

## Line numbers

Inactive code is replaced by spaces, not removed. All line numbers in the output, diagnostics and
source links refer to the original file.
