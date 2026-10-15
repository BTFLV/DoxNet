# Architecture

DoxNet is a pipeline of small stages that communicate through plain dataclasses. No stage depends on
the internals of another, which keeps each one testable in isolation and makes it possible to swap the
parser later without touching the renderers.

```text
config file + command line          config.py      -> Settings
            |
filelist / directory / files        sources.py     -> ordered list of paths
            |
            v
`ifdef evaluation                   preprocess.py  -> same text, inactive code blanked
            |
            v
tokens + doc comments               lexer.py
            |
            v
units, ports, parameters, ...       parser.py      -> DesignUnit + Diagnostic per file
  (comment text: comments.py)
            |
            v
instance resolution, hierarchy      hierarchy.py   -> linked Project
            |
            +--> render/markdown.py
            +--> render/html.py   (+ diagram.py, assets/)
            +--> render/json.py
            +--> render/pdf.py    (Pandoc, from the Markdown)
```

## Modules

`model.py` defines the data passed between stages: `Project`, `DesignUnit`, `Port`, `Parameter`,
`Modport`, `Instance`, `Connection`, `Member`, `FileDoc`, `HierarchyNode` and `Diagnostic`. The JSON
output is `Project.as_dict()` plus a generator stamp, so the schema in `docs/schema/` describes the model
directly.

`preprocess.py` evaluates conditional compilation. It replaces inactive text with spaces and keeps every
line break, so offsets and line numbers stay identical to the original file and no later stage needs a
source map. Macros are tracked across files (one compilation unit) but never expanded.

`lexer.py` produces tokens with character offsets and the list of comments. Comments, strings,
attributes and compiler directives never become identifier tokens, which is what keeps
`string s = "module fake;"` from showing up as a module.

`parser.py` is a declaration-level recognizer. For each unit it reads the header (parameter port list
and port list, ANSI or not), then scans the body for parameters, non-ANSI port declarations, typedefs,
functions, tasks, classes, modports and instantiations. Constructs that cannot contain any of these
(`property`, `covergroup`, `clocking`, `specify`, class bodies, subroutine bodies) are skipped as a
whole. When a header cannot be read, it reports `HDL001` instead of guessing.

Documentation comments are attached in a second step. Each documentable declaration registers an
anchor: the token where it starts (for leading comments) and its name token plus the offset where its
declaration ends (for trailing `///<` comments). A trailing comment only binds to a declaration whose
end comes right before it, which prevents a comment inside a struct body from describing the previous
typedef.

`comments.py` parses comment text into a `DocComment`: brief, paragraphs, named entries (`@port`,
`@parameter`, ...), metadata and lists. It knows nothing about HDL; matching entries to declarations
happens in the parser.

`hierarchy.py` resolves instances against the parsed units, fills `instantiated_by`, marks interface
ports and builds the hierarchy trees with cycle protection.

The renderers only read the linked `Project` and the original source text. `render/html.py` builds the
page directly with escaping at every interpolation; user-provided text goes through Markdown with raw
HTML disabled and is then sanitized with nh3 using a tag allowlist.

## Parser limits

The parser does not elaborate. In particular:

- Expressions are not evaluated. Types and defaults are shown as written.
- Macros are not expanded, so a macro that expands to a module header or a port list is invisible.
- Generate blocks are not unrolled; an instance inside a `for` generate appears once.
- `bind` statements, configurations and library mapping are ignored.
- Classes are listed as members, but their contents are not documented.
- Instances are recognized only in the common `type [#(...)] name [dims] (...)` form at the start of a
  statement. Instances created through macros are not found.

A full frontend such as [slang](https://github.com/MikePopoloski/slang) would remove these limits at
the cost of a heavy native dependency and a strict requirement that the design compiles. Because the
renderers depend only on `model.py`, such a backend can be added as an alternative to `parser.py`
without changing the output side.

## Security

DoxNet reads source files and never executes anything from them. Output file names must be plain
names inside the output directory. `source_url` must be an HTTPS URL without credentials, query or
fragment. The only external program is Pandoc, called with a fixed argument list and only when PDF
output is requested.

## Compatibility

`python DoxNet.py` still works, as do `parse_verilog_file()`, `parse_doxygen_comment()`,
`find_all_units()` and `remove_doxnet_comments()` from DoxNet 1.x and 2.x. `parse_source()` and
`parse_file()` return a tuple-compatible `ParseResult`, so `units, diagnostics = parse_source(text)`
keeps working.
