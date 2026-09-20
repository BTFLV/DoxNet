<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <img src="assets/logo-light.svg" alt="DoxNet logo" width="420">
</picture>

# DoxNet – A Lightweight Documentation Generator for Verilog & SystemVerilog

**DoxNet** is a simple and extensible documentation tool inspired by Doxygen, tailored for **Verilog** and **SystemVerilog**. It parses structured comments in your HDL code and generates **Markdown**, **responsive HTML**, and optionally **PDF** documentation — with a documentation-coverage gate that makes it safe to enforce in CI/CD.

The generated HTML supports both **light and dark themes** (auto-detected, with a manual toggle), includes a **collapsible sidebar**, and works well on both desktop and mobile. Source code is rendered with rich **syntax highlighting** via Pygments.

---

## ✨ Features

- ✅ Doxygen-style annotations:
  - `@brief` – Short description
  - `@input`, `@output`, `@inout` – Signal interface documentation
  - `@parameter`, `@localparam` – Parameter and constant documentation
- ✅ Parses `module`, `interface`, and `package` blocks (Verilog & SystemVerilog)
- ✅ **Documentation-coverage gate** (`--min-coverage` / `--strict`) — fail the build when undocumented modules/interfaces/packages slip through
- ✅ Syntax-highlighted code blocks (collapsible in HTML)
- ✅ Markdown, HTML, and optional PDF generation via Pandoc
- ✅ Fully responsive HTML layout with **light/dark theme toggle**
- ✅ English and German language support
- ✅ Config file support for output file names, file order, and titles
- ✅ Installable CLI (`pip install .` → `doxnet` command) with proper exit codes and logging — built for CI/CD

---

## 📦 Installation

Requires Python 3.8+.

```bash
pip install .
```

This installs the `doxnet` command along with its dependencies ([`markdown`](https://pypi.org/project/Markdown/) and [`pygments`](https://pypi.org/project/Pygments/)).

Optional, for PDF export: [`pandoc`](https://pandoc.org/)

```bash
sudo apt-get install pandoc
```

> Prefer not to install? `python DoxNet.py ...` still works as a drop-in, dependency-light entry point.

---

## 🚀 Usage

### Option 1: CLI Arguments

```bash
doxnet --input <hdl_folder> --output <output_folder> --language en --title "My Project Documentation"
```

### Option 2: Config File

Create a `config.json`:

```json
{
  "title": "My Verilog Documentation",
  "language": "en",
  "html_file": "verilog.html",
  "md_file": "verilog.md",
  "pdf_file": "verilog.pdf",
  "files": [
    "rtl/module1.v",
    "rtl/module2.sv"
  ]
}
```

Run with:

```bash
doxnet --output docs/html/verilog --config config.json
```

### Enforcing documentation in CI

```bash
# fail the build (exit code 2) if less than 90% of modules/interfaces/packages are documented
doxnet --input rtl --output docs --min-coverage 90

# fail on ANY undocumented unit
doxnet --input rtl --output docs --strict
```

Other useful flags: `--no-pdf` (skip Pandoc even if installed), `-v`/`-vv` (more verbose logging), `-q` (warnings/errors only), `--version`.

Exit codes: `0` success, `1` input/config error, `2` coverage gate failed.

---

## 📝 Comment Syntax

Use Doxygen-style comments above your `module`, `interface`, or `package` declarations:

```verilog
/**
 * @brief A simple example module.
 *
 * Demonstrates how to document a Verilog/SystemVerilog module using DoxNet.
 *
 * @parameter WIDTH Bit width of data bus.
 * @localparam DEPTH Internal FIFO depth.
 *
 * @input clk Clock signal.
 * @input rst_n Active-low reset.
 * @input enable Enable signal.
 * @inout data Data bus (bidirectional).
 *
 * @output ready Ready flag.
 */
module example #(parameter WIDTH = 8) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        enable,
  inout  wire [WIDTH-1:0] data,
  output wire        ready
);
  localparam DEPTH = 16;
  // ...
endmodule
```

Also supported:
- `/// @brief One-line style`
- `/// @input clk Clock signal`

---

## 📁 Output Files

| File Name             | Description                                      |
|-----------------------|--------------------------------------------------|
| `verilog.md`          | Raw Markdown file                                |
| `verilog.html`        | Responsive HTML with sidebar, syntax highlighting, and a light/dark theme toggle |
| `verilog.pdf`         | PDF (if Pandoc is available)                     |

> 💡 The HTML output ships both a dark (**Monokai**) and light (**Friendly**) Pygments style; the browser picks one based on the active theme.

---

## 📂 Recommended Output Structure

When generating documentation with DoxNet, your project structure might look like this:

```
docs/
├── verilog-docs-config.json     ← Optional config file for input/output
├── output/                      ← Output directory you define with --output
│   ├── verilog.md               ← Generated Markdown file
│   ├── verilog.html             ← Responsive HTML documentation
│   └── verilog.pdf              ← PDF file (if Pandoc is installed)
```

You can name the output files however you want using the config file (`html_file`, `md_file`, `pdf_file`).

---

## 🤖 CI/CD Example

DoxNet fits nicely in automation and can gate merges on documentation coverage:

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.12"

- name: Install DoxNet
  run: pip install git+https://github.com/BTFLV/DoxNet.git

- name: Generate & verify Verilog documentation
  run: doxnet --output docs/html/verilog --config docs/config.json --min-coverage 90
```

You can deploy `docs/html/verilog` to GitHub Pages or any static host. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) in this repo for a working example that runs the test suite and a `--strict` documentation build.

---

## 🧪 Development

```bash
pip install -e ".[test]"
pytest
```

---

## 📄 License

Released under the **MIT License**.
See the [LICENSE](LICENSE) file for details.
