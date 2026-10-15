# Configuration

Every option can be given on the command line or in a config file. Command-line values override the
config file, which overrides the defaults. `defines` are merged per macro instead of replaced, and
`include_dirs` from both sources are combined.

## Config files

DoxNet reads JSON, TOML, or the `[tool.doxnet]` table of a `pyproject.toml`:

```bash
doxnet --config doxnet.json
doxnet --config doxnet.toml
doxnet --config pyproject.toml
```

Paths inside a config file are relative to the file's directory, not to the current directory.
Unknown keys are an error, so a typo such as `min_coverag` does not silently disable a gate.

```toml
# pyproject.toml
[tool.doxnet]
title = "Video pipeline"
input = "rtl"
output = "build/docs"
exclude = ["**/generated/*", "sim/*"]
include_dirs = ["rtl/include"]
defines = { SYNTHESIS = "", BUS_WIDTH = "64" }
top = ["video_top"]
formats = ["html", "json"]
source_url = "https://github.com/acme/video/blob/main/rtl"
min_coverage = 100
min_port_coverage = 90
fail_on_warnings = true
disable = ["DOC004"]
```

TOML needs Python 3.11 or the `tomli` package, which is installed automatically on older versions.

## Reference

| Config key | Command line | Default | Description |
|---|---|---|---|
| `title` | `--title` | `Project Documentation` | Document title |
| `language` | `--language` | `en` | Labels: `en` or `de` |
| `input` | `-i`, `--input` | | Directory searched recursively for `.v`, `.sv`, `.vh`, `.svh` |
| `files` | | | Explicit list of files, processed in this order |
| `filelist` | `-f`, `--filelist` | | Simulator-style `.f` file, see [Inputs](inputs.md) |
| `exclude` | `--exclude` | | Globs relative to the input root (repeatable) |
| `encoding` | `--encoding` | `utf-8` | Encoding of all source files |
| `defines` | `-D NAME[=VALUE]` | | Macros for `` `ifdef `` evaluation; object or `["A", "B=1"]` |
| `include_dirs` | `--incdir` | | Search path for `` `include `` |
| `preprocess` | `--no-preprocess` | `true` | Evaluate conditional compilation |
| `plain_comments` | `--plain-comments` | `false` | Use trailing `//` comments as descriptions |
| `top` | `--top` | | Roots of the hierarchy view (default: every uninstantiated module) |
| `include_source` | `--no-source` | `true` | Embed the source code |
| `source_url` | `--source-url` | | HTTPS prefix for links to the repository |
| `output` | `-o`, `--output` | | Output directory |
| `formats` | `--formats html,json` | all four | Subset of `html`, `markdown`, `json`, `pdf` |
| | `--no-pdf` | | Drop `pdf` from the formats |
| `pdf_required` | `--pdf-required` | `false` | Fail if Pandoc cannot produce the PDF |
| `html_file` | `--html-file` | `documentation.html` | File name inside the output directory |
| `md_file` | `--md-file` | `documentation.md` | |
| `json_file` | `--json-file` | `documentation.json` | |
| `pdf_file` | `--pdf-file` | `documentation.pdf` | |
| | `--check` | | Run everything but write no files; `--output` is not needed |
| `min_coverage` | `--min-coverage` | | Minimum percentage of documented units |
| `min_port_coverage` | `--min-port-coverage` | | Minimum percentage of documented ports |
| `min_parameter_coverage` | `--min-parameter-coverage` | | Minimum percentage of documented parameters |
| `strict` | `--strict` | `false` | Same as `min_coverage = 100` |
| `fail_on_warnings` | `--fail-on-warnings` | `false` | Exit with 3 if any warning remains |
| `disable` | `--disable DOC004,DOC005` | | Warning codes to suppress |
| | `--diagnostics-format github` | `text` | Print GitHub workflow annotations |
| | `-v`, `-vv`, `-q` | | More or less logging |

Output file names must be plain names, not paths, and must differ from each other. The PDF is
converted from the Markdown output, so `pdf` requires `markdown` in `formats`.

## Quality gates

Coverage is the number of documented entities divided by the number found:

- units with a documentation comment,
- ports with a description,
- overridable parameters with a description.

When there is nothing to count, the percentage is `null` ("n/a"), not 100 %. A threshold on an empty
category therefore fails: a gate on port coverage for a project without ports is almost certainly a
configuration mistake. An input without any design unit is an error.

```bash
# every unit documented, at least 90 % of the ports, no warnings
doxnet -c doxnet.json --strict --min-port-coverage 90 --fail-on-warnings
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Invalid configuration or input, including HDL and preprocessor errors. Nothing is written. |
| 2 | A coverage threshold was not met. The output is still written. |
| 3 | An output could not be written, a required PDF failed, or `--fail-on-warnings` found warnings |
