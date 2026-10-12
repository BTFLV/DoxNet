<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <img src="assets/logo-light.svg" alt="DoxNet" width="420">
</picture>

# DoxNet

**HDL-aware documentation and interface validation for Verilog/SystemVerilog.**

DoxNet reads RTL source files, extracts module/interface/package declarations, their ports and parameters, merges Doxygen-style comments with the actual HDL interfaces, and generates **Markdown**, **searchable static HTML**, **JSON**, and optionally **PDF**. It reports missing documentation as coverage metrics and warns when comments refer to ports or parameters that no longer exist.

> **Parser scope:** DoxNet 2.1 uses a conservative, source-aware lexical/header parser. It does **not** yet fully parse or elaborate IEEE 1800 SystemVerilog. Macro expansion, `ifdef evaluation, complex header declarations, and elaborated instance hierarchies need a full HDL frontend. See [Limitations](#limitations) and [Architecture](docs/ARCHITECTURE.md).

## Features

- Doxygen-like `/** ... */` or consecutive `///` comments: `@brief`, `@port`, `@input`, `@output`, `@inout`, `@parameter`, `@localparam`.
- Auto-extracted **port names, directions, type/width expressions**, plus **parameter names, types and defaults**; does not require duplicate interface declarations in comments.
- Documented **and undocumented** design units appear in the output.
- **Unit, port and parameter documentation coverage** with separate CI thresholds.
- Warnings for stale, duplicate or direction-mismatched annotations; optional CI failure on warnings.
- Responsive standalone HTML with search, syntax highlighting, light/dark toggle, navigation and collapsible source; no external CSS/JS at runtime.
- Machine-readable JSON output with stable `schema_version`, source locations, diagnostics and coverage metrics.
- Config files, explicit file order, nested filelists, exclusion globs, English/German labels, and direct HTTPS source links.
- Installable CLI and backward-compatible `python DoxNet.py` wrapper.
- pytest regressions and GitHub Actions for Linux, Windows and macOS.

## Installation

Requires **Python 3.9+**.

```bash
pip install .
doxnet --version
```

For development:

```bash
pip install -e ".[test]"
pytest -q
ruff check src tests
```

PDF output optionally requires [Pandoc](https://pandoc.org/) plus a compatible PDF engine (usually LaTeX). Without Pandoc, HTML, Markdown and JSON still generate successfully unless `--pdf-required` is specified.

## Quick start

```bash
doxnet --input examples/rtl --output docs/output --no-pdf

# Or try the checked-in configuration, including coverage thresholds
doxnet --config examples/doxnet.json --output docs/output --no-pdf
```

Expected outputs:

| File | Purpose |
|---|---|
| `documentation.html` | Standalone searchable HTML with source code |
| `documentation.md` | Markdown manual including interface tables |
| `documentation.json` | Structured units, ports, parameters, diagnostics and coverage |
| `documentation.pdf` | Optional Pandoc export |

### Example source

```systemverilog
/**
 * @brief Configurable counter
 * @parameter WIDTH Width of the counter
 * @input clk Clock input
 * @input rst_n Active-low reset
 * @output count Current count
 */
module counter #(parameter int WIDTH = 16) (
    input  logic clk,
    input  logic rst_n,
    output logic [WIDTH-1:0] count
);
endmodule
```

The generated tables read `WIDTH = 16`, the `logic [WIDTH-1:0]` range and port directions from the declaration itself. The comment supplies only their descriptions. Prefer the neutral `@port <name> <description>` form for new projects; `@input`, `@output`, and `@inout` remain supported and additionally check the direction.

### Documentation quality gates

```bash
# Fail if fewer than 90% of design units are documented
doxnet -i rtl -o docs/output --no-pdf --min-coverage 90

# Strict is backward-compatible: requires 100% design-unit coverage
doxnet -i rtl -o docs/output --no-pdf --strict

# Also validate the documented interface
# These thresholds fail when a unit exposes undocumented ports/parameters.
doxnet -i rtl -o docs/output --no-pdf \
    --strict --min-port-coverage 100 --min-parameter-coverage 100 \
    --fail-on-warnings
```

Coverage uses the number of documented entities divided by the number of discovered entities. **A zero denominator is `null`/N/A, never 100%.** An input with no design units is an error. A requested coverage threshold with zero ports/parameters fails because no meaningful coverage can be calculated.

CLI exit codes: `0` success; `1` configuration/input error; `2` coverage failure; `3` output/required PDF failure or warnings when `--fail-on-warnings` is set.

### Config file and explicit file order

Example `doxnet.json` (file paths are relative to the config's directory):

```json
{
  "title": "FPGA Project",
  "language": "en",
  "files": ["rtl/top.sv", "rtl/fifo.sv"],
  "html_file": "index.html",
  "json_file": "interfaces.json",
  "min_coverage": 90,
  "min_port_coverage": 80,
  "exclude": ["**/generated/*.sv"]
}
```

```bash
doxnet --config doxnet.json --output docs/output --no-pdf
```

An immediately usable configuration is checked in at [examples/doxnet.json](examples/doxnet.json). The explicit order in `files` is respected. **Explicit CLI options override JSON values**, which override defaults. Alternatively use `--input rtl`, or `--filelist project.f` with one relative source path per line, `#` or `//` comments, and nested `-f other.f` entries. Options `+incdir`, `+define`, etc. are intentionally rejected rather than silently ignored; compilation/preprocessing options are not yet supported.

Useful flags: `--exclude 'generated/*'` (repeatable), `--no-source`, `--source-url https://github.com/OWNER/REPO/blob/main`, `--no-pdf`, `--pdf-required`, `-v`/`-vv`, `-q`, and `--version`. Run `doxnet --help` for all flags.

## JSON output

`documentation.json` contains `schema_version: 1`, `title`, `files`, `units`, `diagnostics`, and `coverage`. Each design unit has `kind`, `name`, `file`, `line`, `end_line`, `brief`, `description`, `documented`, `ports`, `parameters`, and `localparams`. Coverage includes independent `units`, `ports`, and `parameters` counts and percentages. JSON is intended for CI reporting and other tooling.

## CI/CD

The repository workflow runs tests and Ruff checks on multiple Python versions/operating systems, generates documentation with strict coverage gates, builds a wheel and uploads the example documentation as a workflow artifact. Integrate into a project workflow with:

```yaml
- name: Install DoxNet
  run: pip install git+https://github.com/BTFLV/DoxNet.git
- name: Generate and validate HDL docs
  run: doxnet -i rtl -o docs/output --no-pdf --strict --min-port-coverage 90
```

## Limitations

The bundled parser is deliberately lightweight and does not implement full language semantics. Malformed headers or missing unit terminators are diagnosed as input errors; documentation comments with known tags that do not immediately precede a unit are reported as warnings. It supports common ANSI/non-ANSI module headers, interfaces, packages, parameter lists and localparam declarations. It **does not** expand includes/macros, resolve conditional compilation, evaluate expressions, elaborate parameters or instances, or guarantee correct extraction from every legal SystemVerilog construct. Both branches of a `` `ifdef `` may be counted without preprocessing; do not rely on unpreprocessed coverage for conditional RTL. A serious future milestone is a parser backend using [slang/pyslang](https://github.com/MikePopoloski/slang). Treat reported values as extracted source expressions, **not evaluated bit widths**.

Do not use DoxNet coverage as a substitute for synthesizer/compiler diagnostics. If an extraction looks wrong, provide a minimal RTL reproducer in an issue.

## Project

- [Architecture and parser boundaries](docs/ARCHITECTURE.md)
- [Contributing and running tests](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security policy](SECURITY.md)
- [MIT license](LICENSE)