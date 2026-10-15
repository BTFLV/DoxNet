# Using DoxNet in CI

The typical setup checks documentation on every pull request and publishes the HTML from the main
branch.

## GitHub Actions

The repository is usable as an action. It installs DoxNet from the referenced tag or branch and prints
diagnostics as pull request annotations.

```yaml
name: HDL docs

on:
  pull_request:
  push:
    branches: [main]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: BTFLV/DoxNet@v3.0.0
        with:
          args: --config doxnet.json --output build/hdl-docs --no-pdf
      - uses: actions/upload-artifact@v4
        with:
          name: hdl-docs
          path: build/hdl-docs
```

To publish on GitHub Pages, set `html_file` to `index.html` and add the
[pages actions](https://github.com/actions/deploy-pages) after the DoxNet step.

Without the action:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install git+https://github.com/BTFLV/DoxNet.git@v3.0.0
      - run: doxnet --config doxnet.json --check --diagnostics-format github
```

## GitLab CI

```yaml
hdl-docs:
  image: python:3.12-slim
  script:
    - pip install git+https://github.com/BTFLV/DoxNet.git@v3.0.0
    - doxnet --config doxnet.json --output public --no-pdf
  artifacts:
    paths: [public]
```

## pre-commit

```yaml
repos:
  - repo: https://github.com/BTFLV/DoxNet
    rev: v3.0.0
    hooks:
      - id: doxnet
        args: [--config, doxnet.json]
```

The hook runs `doxnet --check`, which parses everything and applies the gates without writing files.

## Introducing gates in an existing project

Turning on `--strict` in a large, mostly undocumented code base fails immediately and stays red. A
ratchet works better:

1. Run once without gates and note the reported coverage.
2. Set `min_coverage`, `min_port_coverage` and `min_parameter_coverage` slightly below those numbers.
3. Raise them as documentation is added.

Enable `fail_on_warnings` early. Warnings such as `DOC001` (a comment describes a port that no longer
exists) are cheap to fix when they appear and expensive to clean up later.

The JSON report is useful for tracking coverage over time:

```bash
jq '.coverage | map_values(.percent)' build/hdl-docs/documentation.json
```
