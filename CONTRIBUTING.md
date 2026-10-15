# Contributing to DoxNet

Bug reports with a small piece of RTL that shows the problem are the most useful contribution. If
DoxNet extracts something wrong, please include the source, what you expected, and the relevant part of
`documentation.json`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
pytest
ruff check src tests
doxnet -c examples/doxnet.json -o build/example
```

## Tests

| File | Covers |
|---|---|
| `tests/test_parser.py` | Unit headers and the 2.x compatibility API |
| `tests/test_extraction.py` | Member comments, body declarations, instances, hierarchy, lexer |
| `tests/test_comments.py` | Comment text and tags |
| `tests/test_preprocess.py` | `` `ifdef `` evaluation, includes, defines |
| `tests/test_render.py` | HTML/Markdown/JSON output and escaping |
| `tests/test_cli.py` | Options, config files, filelists, exit codes, the example project |

A parser fix should come with a test that fails without it. Keep reproducers minimal; a three-line
module is easier to reason about than a real design.

## Pull requests

- Keep each pull request to one change and describe the behavior before and after.
- Update the documentation in `docs/` and the changelog for anything users notice.
- The JSON report is an interface. Adding fields is fine; renaming, removing or changing the meaning of
  a field needs a new `schema_version` and an update of `docs/schema/doxnet.schema.json`.
- Keep the generated HTML self-contained: no CDN links, no external fonts.
- Do not claim support for a language feature without tests for it.
