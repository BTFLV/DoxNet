# Changelog

## [2.1.0] - Unreleased

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