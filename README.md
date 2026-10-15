<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <img src="assets/logo-light.svg" alt="DoxNet" width="420">
</picture>

# DoxNet

DoxNet generates documentation for Verilog and SystemVerilog designs and checks that it stays correct.

It reads the RTL, takes ports, parameters, types and instances from the declarations, and combines them
with Doxygen-style comments. The result is a standalone HTML page, Markdown, JSON and optionally PDF.
In CI, it fails the build when documentation coverage drops or when a comment describes a port that no
longer exists.

```systemverilog
/**
 * @brief Single-clock FIFO with registered outputs.
 * @note DEPTH must be a power of two.
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

Widths, directions and defaults come from the code. The comments only add what the code cannot say.

## Features

- Modules, interfaces, packages, programs and UDPs with ANSI and non-ANSI headers
- Ports, parameters, local parameters, modports, typedefs, functions, tasks and instances
- Leading (`/** */`, `///`) and trailing (`///<`) comments on every declaration, or tags in the unit
  comment (`@port`, `@parameter`, `@modport`, ...)
- Design hierarchy with links between units, "instantiated by" references and unresolved (vendor) cells
- `` `ifdef ``/`` `elsif ``/`` `else `` evaluation with `-D` defines, include directories and filelists
- Standalone HTML with search, port block diagrams, light and dark theme and linked, highlighted source
- JSON report with a published [JSON Schema](docs/schema/doxnet.schema.json)
- Coverage gates for units, ports and parameters, and checks for stale, duplicate or misspelled tags
- GitHub Action, pre-commit hook and pull request annotations

## Installation

Python 3.9 or newer.

```bash
pip install git+https://github.com/BTFLV/DoxNet.git
doxnet --version
```

PDF output needs [Pandoc](https://pandoc.org/) and a LaTeX engine. Everything else works without them.

## Usage

```bash
# Document every .v/.sv/.vh/.svh below rtl/
doxnet --input rtl --output build/docs

# With macros and include paths, as for the simulator
doxnet --filelist sim/files.f -D SYNTHESIS --incdir rtl/include --output build/docs

# Check only, as a CI gate: all units documented, 90 % of ports, no warnings
doxnet --input rtl --check --strict --min-port-coverage 90 --fail-on-warnings
```

For anything beyond a quick run, put the options in a config file:

```json
{
  "title": "UART example",
  "input": "rtl",
  "include_dirs": ["rtl/include"],
  "output": "build/docs",
  "html_file": "index.html",
  "min_coverage": 100,
  "min_port_coverage": 100,
  "fail_on_warnings": true
}
```

```bash
doxnet --config doxnet.json
```

TOML and `[tool.doxnet]` in `pyproject.toml` work as well. The [example project](examples/) is a small
UART with a package, an interface, a FIFO and a top level; `doxnet -c examples/doxnet.json -o out`
renders it.

## Documentation

- [Writing documentation comments](docs/writing-documentation.md): comment forms and all tags
- [Configuration](docs/configuration.md): every option, quality gates, exit codes
- [Inputs and preprocessing](docs/inputs.md): file selection, filelists, `` `ifdef `` handling
- [Output formats](docs/output.md): HTML, Markdown, PDF and the JSON report
- [Diagnostics](docs/diagnostics.md): what each warning and error means
- [CI integration](docs/ci.md): GitHub Actions, GitLab, pre-commit
- [Architecture](docs/ARCHITECTURE.md): how the pipeline works and where the parser stops

## Limits

DoxNet parses declarations; it does not elaborate the design. Expressions are shown as written, macros
are not expanded, and generate loops are not unrolled. It handles the constructs found in typical RTL,
but it is not a substitute for a compiler: if an extraction looks wrong, please open an issue with a
small reproducer. Details are in [Architecture](docs/ARCHITECTURE.md#parser-limits).

## Upgrading from 2.x

See the [changelog](CHANGELOG.md). In short: `` `ifdef `` is now evaluated (use `--no-preprocess` for
the old behavior), the JSON report is `schema_version` 2 with only additions, and unknown config keys
are rejected. The command line and the Python helpers from 2.x keep working.

## Development

```bash
pip install -e ".[test]"
pytest
ruff check src tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md). DoxNet is released under the [MIT license](LICENSE).
