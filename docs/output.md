# Output formats

Each run writes up to four files into the output directory. `--formats` (config: `formats`) selects
which.

## HTML

A single standalone file with all styles and scripts inlined. It can be opened from disk, attached to a
ticket, or published as a static page. It contains:

- an overview with coverage per category,
- the design hierarchy, starting at every module nothing else instantiates (or at `--top`),
- per file: the `@file` description, every design unit, and the highlighted source with line anchors,
- per unit: a block diagram of its ports, tables for parameters, ports, modports, local parameters and
  instances, types and subroutines, "instantiated by" links, notes, warnings and to-dos,
- a per-unit coverage table and the list of diagnostics.

Search filters both the sidebar and the page. Press `/` to focus it, `Enter` to jump to the first
match and `Esc` to clear it. The light/dark theme follows the system setting and can be toggled.

Source locations link into the embedded source. With `--source-url`, they link to the repository
instead, e.g. `https://github.com/acme/video/blob/main/rtl/fifo.sv#L12`. `--no-source` leaves the
source out entirely.

Text from comments is rendered as Markdown with raw HTML disabled, and the result is sanitized with
an allowlist before it is embedded. A comment cannot inject markup or scripts into the page.

## Markdown

GitHub Flavored Markdown with the same content as the HTML page, minus the block diagrams. Units have
stable anchors, so links between units work on GitHub and in most Markdown viewers.

## PDF

If [Pandoc](https://pandoc.org) and a LaTeX engine are installed, the Markdown file is converted to
PDF. If Pandoc is missing, DoxNet logs a warning and carries on; use `--pdf-required` to make that an
error, or `--no-pdf` to skip it.

## JSON

Intended for scripts, dashboards and CI checks. The format is described by a JSON Schema in
[schema/doxnet.schema.json](schema/doxnet.schema.json); the test suite validates the example output
against it.

```json
{
  "schema_version": 2,
  "generator": {"name": "doxnet", "version": "3.0.0"},
  "title": "UART example",
  "files": ["stream_pkg.sv", "sync_fifo.sv", "uart_top.sv"],
  "units": [
    {
      "kind": "module",
      "name": "sync_fifo",
      "file": "sync_fifo.sv",
      "line": 11,
      "documented": true,
      "ports": [{"name": "clk", "direction": "input", "type": "logic", "description": "Clock", "line": 15}],
      "parameters": [{"name": "WIDTH", "type": "int", "default": "8", "description": "Data width in bits",
                      "line": 12, "local": false}],
      "instances": [],
      "instantiated_by": ["uart_top"]
    }
  ],
  "top": ["uart_top"],
  "hierarchy": [{"module": "uart_top", "instance": "", "resolved": true, "recursive": false, "children": []}],
  "coverage": {
    "units": {"documented": 5, "total": 5, "percent": 100.0},
    "ports": {"documented": 20, "total": 20, "percent": 100.0},
    "parameters": {"documented": 7, "total": 7, "percent": 100.0}
  },
  "diagnostics": []
}
```

(Shortened; see the schema for every field.)

A few things to keep in mind:

- `type` and `default` are source text with whitespace normalized. Nothing is evaluated, so
  `[WIDTH-1:0]` stays symbolic.
- `percent` is `null` when there is nothing to count.
- An instance is `resolved` when its module or interface is one of the inputs. Vendor primitives and
  IP that is not part of the inputs show up as unresolved; they are not an error.

`schema_version` changes only when existing fields change meaning or disappear. New fields may be
added within a version.

### Changes from schema version 1

Version 2 (DoxNet 3.0) adds `generator`, `file_docs`, `top`, `hierarchy`, and on each unit
`modports`, `instances`, `members`, `metadata`, `deprecated`, `notes`, `warnings`, `todos`, `see` and
`instantiated_by`. All version 1 fields are unchanged.
