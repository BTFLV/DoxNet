# DoxNet architecture

DoxNet's pipeline is deliberately small and split into testable boundaries:

```text
RTL source + config / filelist
       |
       v
parser.lex() -> tokens and Doxygen comment blocks
       |
       v
parser.parse_source() -> DesignUnit / Port / Parameter + Diagnostic
       |
       v
Project (model.py) -> coverage() and JSON schema
       |
       +--> Markdown
       +--> HTML + code highlighting + HTML sanitization
       +--> JSON
       +--> optional Pandoc PDF
```

## Models

`DesignUnit` captures type (`module`, `interface`, `package`), source location, documentation and its interface. `Port` records direction, source type/range expression, description and location. `Parameter` records declaration type, default expression and description. `Diagnostic` contains a stable code, severity, file and line. `Project` holds ordered files, extracted units, diagnostics and coverage metrics.

The renderer **does not parse source files**. It accepts a `Project` and an ordered mapping of original source text and generates artifacts. Source snippets are syntax highlighted; their content is not evaluated.

## Parser scope

The default extractor lexes strings, comments and tokens separately so strings such as `"module phantom"` do not inflate coverage. It associates documentation only when a comment is immediately followed by a design-unit declaration (whitespace is allowed). It parses common module headers and matches `@port`/`@parameter` annotations against discovered declarations.

This is *not* a preprocessor, elaborator, or fully compliant SystemVerilog parser. Unsupported cases include macros and conditional compilation, complex package imports in module headers, interface modport semantics, classes, compilation-unit definitions, generated hierarchies and evaluated parameter widths. The filelist reader intentionally rejects preprocessor flags that it cannot honor.

A future `pyslang` backend should replace only the token/header extraction step while producing the same typed model. This prevents downstream formatters from depending on a particular parser's AST and gives tests a stable API.

## Security boundaries

CLI filenames are restricted to basenames beneath the output directory. User-supplied document text is escaped before Markdown conversion and the HTML fragment is sanitized with an allowlist (Bleach); the outer HTML template and client-side search script are trusted DoxNet code. The optional source URL must be HTTPS. DoxNet reads source; it never executes HDL.

## Coverage contract

- **Units:** a unit has an associated, nonempty Doxygen comment.
- **Ports:** a discovered port has a nonempty description matching its name.
- **Parameters:** a discovered module parameter has a nonempty description.
- **No entities:** `percent: null`, not `100`; zero units is a CLI input error.
- **Strict:** 100% unit coverage only, to preserve v2.0 CLI semantics.

Existing v2.0 `parse_verilog_file()` remains as a compatibility wrapper. `parse_source()` / `parse_file()` and the dataclasses are preferred for new integrations.
