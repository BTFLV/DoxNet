# Contributing to DoxNet

Contributions and reproducible SystemVerilog edge cases are welcome.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[test]"
ruff check src tests
pytest -q
python DoxNet.py -i examples/rtl -o docs/output --no-pdf --strict --min-port-coverage 100
```

## Pull requests

- Open a focused PR with a description of the behavior change.
- Include a minimal `.sv` reproducer and regression test for parser issues.
- Update the README and `CHANGELOG.md` for user-facing behavior changes.
- Keep the JSON `schema_version` and the old CLI flags stable, or explicitly document compatibility breaks.
- Do not claim full IEEE 1800 support without parsing, preprocessing and elaboration tests.

## Tests

`tests/test_parser.py` validates extraction and corner cases; `tests/test_cli.py` covers configuration, exit codes and coverage; `tests/test_render.py` checks generated HTML/Markdown/JSON and injection protections.