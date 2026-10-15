# Changelog

## [3.0.0] - 2026-10-15

### Added

- Conditional compilation: `` `ifdef ``, `` `ifndef ``, `` `elsif ``, `` `else `` and IEEE 1800-2023
  expressions are evaluated. Macros come from `-D`/`defines`, filelist `+define+`, `` `define `` in
  the sources and headers found through `` `include `` with `--incdir`/`include_dirs`.
- Member comments: leading `/** */`/`///` and trailing `///<`/`//!<`/`/**< */` on ports, parameters,
  local parameters, typedefs, functions, tasks, modports and instances.
- Optional use of ordinary trailing `//` comments as port descriptions (`--plain-comments`).
- Extraction of typedefs, functions, tasks, classes, interface modports and module/interface
  instances with parameter overrides and connections.
- Design hierarchy with "instantiated by" links, configurable roots (`--top`) and detection of
  duplicate unit names (`HDL002`).
- Programs and UDPs (`primitive`); body `parameter` declarations; header `localparam`s; interface
  ports (`bus_if.mp name`).
- New tags: `@details`, `@deprecated`, `@note`, `@warning`, `@todo`, `@see`, `@author`, `@version`,
  `@since`, `@date`, `@copyright`, `@license`, `@file`, `@modport`, `@instance`, `@param` with
  `[in]`/`[out]`, and `\tag` syntax. Tag text may continue over several lines.
- Diagnostics for unknown tags (`DOC005`), empty descriptions (`DOC006`) and preprocessor problems
  (`PP001`-`PP003`).
- Redesigned HTML: overview with coverage, hierarchy tree, SVG block diagrams of each unit's ports,
  per-unit coverage, diagnostics list, keyboard search, source with line anchors.
- Markdown output with cross-links between units, hierarchy and per-unit coverage.
- TOML config files and `[tool.doxnet]` in `pyproject.toml`; every option can now be set in a config.
- `--check` (no output), `--formats`, `--disable`, `--diagnostics-format github`, `--encoding`.
- Filelists: `-F`, `+incdir+`, `+define+`, environment variables, several files per line.
- JSON Schema for the report in `docs/schema/`, `python -m doxnet`, GitHub Action, pre-commit hook.
- User documentation in `docs/`.

### Changed

- JSON `schema_version` is 2. All version 1 fields keep their meaning; see `docs/output.md`.
- Inactive `` `ifdef `` branches are no longer parsed or counted. `--no-preprocess` restores the old
  behavior.
- Without `@brief`, the first paragraph of a comment becomes the brief description.
- A comment still documents a unit when ordinary comments or compiler directives stand between them.
- Unknown keys in a config file are an error.
- HTML sanitizing uses nh3 instead of the unmaintained bleach.
- Types and default values are shown with normalized whitespace and without comments.

### Fixed

- `virtual interface` and top-level `class`/`extern module` declarations no longer cause bogus parse
  errors.
- A port following an interface port no longer inherits the `interface` direction.
- Attributes such as `(* keep *)` before a port no longer hide its direction.
- `assert property (...)` no longer hides the rest of a module body.
- Markdown code spans are used instead of inline HTML, so names no longer disappear from the PDF.

## [2.1.0] - 2026-10-12

### Added

- Typed representation of design units, ports, parameters, diagnostics and coverage.
- Automatic interface and parameter extraction from common HDL declarations.
- `@port` documentation tags with validation of stale/duplicate/mismatched entries.
- Port and parameter coverage gates (`--min-port-coverage`, `--min-parameter-coverage`).
- Searchable HTML, direct source links, JSON output with schema version and structured diagnostics.
- Explicit file ordering, nested simple filelists and exclusion patterns.
- Expanded regression tests and multi-OS CI with wheel smoke test.

### Changed

- Documentation includes undocumented design units, with missing documentation indicated.
- Empty projects no longer report 100% coverage.
- Config values are validated; CLI arguments take precedence over JSON config.
- HTML content generated from comments is sanitized; output paths are restricted to the chosen directory.
- Minimum Python version is 3.9.

### Compatibility

- `python DoxNet.py`, the `doxnet` command, legacy tags and `parse_verilog_file()` remain available.
- `--strict` continues to apply only to design-unit coverage.
- The parser is still a lightweight lexical/header extractor, not a full HDL compiler.

## [2.0.0] - 2026-09-20

- Split initial script into installable package; added SystemVerilog units, CI and coverage gate.