# DoxNet – A Lightweight Documentation Generator for Verilog

**DoxNet** is a simple and extensible documentation tool inspired by Doxygen, tailored for **Verilog HDL**. It parses structured comments in your Verilog code and generates **Markdown**, **responsive HTML**, and optionally **PDF** documentation.

The generated HTML is styled with a GitHub-inspired **dark theme**, includes a **collapsible sidebar**, and works well on both desktop and mobile. Verilog source code is rendered with rich **syntax highlighting** (Monokai theme) using Pygments.

---

## ✨ Features

- ✅ Doxygen-style annotations:
  - `@brief` – Short module description
  - `@input`, `@output`, `@inout` – Signal interface documentation
  - `@parameter`, `@localparam` – Parameter and constant documentation
- ✅ Syntax-highlighted Verilog code blocks (collapsible in HTML)
- ✅ Markdown, HTML, and optional PDF generation via Pandoc
- ✅ Fully responsive HTML layout (mobile-friendly)
- ✅ Dark theme with Pygments **Monokai** syntax highlighting
- ✅ English and German language support
- ✅ Config file support for output file names, file order, and titles
- ✅ Ready for CI/CD workflows (e.g., GitHub Actions)

---

## 📦 Installation

### Requirements

- Python 3
- [`markdown`](https://pypi.org/project/Markdown/):
  ```bash
  pip install markdown
  ```
- [`pygments`](https://pypi.org/project/Pygments/) for syntax highlighting:
  ```bash
  pip install pygments
  ```
- Optional for PDF export: [`pandoc`](https://pandoc.org/)
  ```bash
  sudo apt-get install pandoc
  ```

---

## 🚀 Usage

### Option 1: CLI Arguments

```bash
python DoxNet.py --input <verilog_folder> --output <output_folder> --language en --title "My Project Documentation"
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
    "rtl/module2.v"
  ]
}
```

Run with:

```bash
python DoxNet.py --output docs/html/verilog --config config.json
```

---

## 📝 Comment Syntax

Use Doxygen-style comments above your Verilog modules:

```verilog
/**
 * @brief A simple example module.
 *
 * Demonstrates how to document a Verilog module using DoxNet.
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
| `verilog.html`        | Responsive, dark-themed HTML with sidebar & syntax highlighting |
| `verilog.pdf`         | PDF (if Pandoc is available)                     |

> 💡 HTML uses [Pygments](https://pygments.org/) with **Monokai** style for Verilog syntax highlighting.

---

## 📂 Recommended Output Structure

When generating Verilog documentation with DoxNet, your project structure might look like this:

```
docs/
├── DoxNet.py                    ← The DoxNet script (optional if used externally)
├── verilog-docs-config.json     ← Optional config file for input/output
├── output/                      ← Output directory you define with --output
│   ├── verilog.md               ← Generated Markdown file
│   ├── verilog.html             ← Responsive HTML documentation
│   └── verilog.pdf              ← PDF file (if Pandoc is installed)
```

You can name the output files however you want using the config file (`html_file`, `md_file`, `pdf_file`).

---

## 🤖 CI/CD Example

DoxNet fits nicely in automation:

```yaml
- name: Generate Verilog Documentation
  run: |
    python DoxNet.py --output docs/src/html/verilog --config docs/config.json
```

You can deploy `docs/src/html/` to GitHub Pages or any static host.

---

## 📄 License

Released under the **MIT License**.  
See the [LICENSE](LICENSE) file for details.