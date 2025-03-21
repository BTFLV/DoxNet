# DoxNet - A Lightweight Documentation Generator for Verilog

DoxNet is a simple, Doxygen-like tool designed to generate documentation for Verilog files. It extracts specially formatted comments and creates structured documentation in Markdown, HTML, and PDF formats. The generated HTML is styled with a GitHub-like dark theme and features a sidebar for easy navigation.

## Features

- **Supports Doxygen-style comments** for documenting Verilog modules, including:
  - `@brief` — Short module description.
  - `@input` — Defines input signals.
  - `@ouput` — Defines output signals. *(Note: The tag `@ouput` instead of `@output` is used for compatibility.)*
  - `@parameter` — Lists module parameters.
  - `@localparam` — Lists internal local parameters.
- **Processes multiple Verilog files** recursively in a given directory.
- **Generates Markdown, HTML, and optionally PDF**.
- **Customizable output**, allowing language selection (`en` or `de`) and documentation title changes.
- **Responsive HTML design**, optimized for both desktop and mobile, with a collapsible sidebar.

---

## Installation

### 1. Install Python Dependencies

Ensure you have Python 3 installed. Install the required dependencies:

```bash
pip install markdown
```

For PDF generation, [Pandoc](https://pandoc.org/installing.html) is required:

```bash
sudo apt-get install pandoc
```

---

## Usage

Run the script with the desired input and output directories:

```bash
python DoxNet.py --input <verilog_folder> --output <documentation_folder>
```

### Command-line Options

| Option            | Description                                                   |
|------------------|--------------------------------------------------------------|
| `--input -i`     | **(Required)** The directory containing Verilog files.       |
| `--output -o`    | **(Required)** The output directory for documentation.       |
| `--language`     | Select documentation language: `en` (default) or `de`.       |
| `--title`        | Customize the title of the documentation.                    |

Example:

```bash
python DoxNet.py --input src/verilog --output docs --language en --title "Verilog Documentation"
```

This generates:
- `documentation.md` → Markdown documentation.
- `documentation.html` → Dark-themed, responsive HTML documentation.
- `documentation.pdf` (if Pandoc is installed) → PDF version.

---

## Formatting Verilog Comments

DoxNet relies on **Doxygen-style comments** in your Verilog files. Use the following format:

```verilog
/**
 * @brief A simple example module.
 *
 * This module is used to demonstrate how to write documentation comments
 * for Verilog files. It includes inputs, outputs, and parameters.
 *
 * @parameter WIDTH  Defines the bit-width of the data.
 * @localparam DEPTH Internal storage depth.
 *
 * @input clk       System clock signal.
 * @input rst_n     Active-low reset signal.
 * @input enable    Enable signal for operation.
 * @input data_in   Data input signal.
 *
 * @ouput data_out  Data output signal.
 */
module example_module #(
  parameter WIDTH = 8
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        enable,
  input  wire [WIDTH-1:0] data_in,
  output wire [WIDTH-1:0] data_out
);
  localparam DEPTH = 16;
  // Module implementation...
endmodule
```

### Supported Comment Formats

- **Block Comments (`/** ... */`)** → Used for module-level descriptions.
- **Single-line Comments (`/// ...`)** → Used for brief inline documentation.

---

## Output Structure

### **Markdown (`documentation.md`)**
The Markdown file provides a clean, structured representation of the documentation, including module descriptions, parameters, and signal lists.

### **HTML (`documentation.html`)**
The HTML output features:
- **Dark mode styling** for readability.
- **Sidebar navigation** with a collapsible menu on mobile.
- **Automatic link generation** for easy reference.

### **PDF (`documentation.pdf`)** *(Optional)*
If Pandoc is installed, a PDF version of the documentation is generated.

---

## Integration with CI/CD

DoxNet can be used in automated workflows (e.g., GitHub Actions, GitLab CI/CD) to generate documentation as part of a continuous integration pipeline.

Example workflow:
```yaml
- name: Generate Verilog Documentation
  run: |
    python DoxNet.py --input rtl --output docs
    mv docs/documentation.html docs/rtl.html
    mv docs/documentation.pdf docs/verilog-docs.pdf
```

This ensures that the Verilog documentation is generated and placed in the appropriate directory for deployment.

---

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests to improve DoxNet.

---

## License

DoxNet is released under the **MIT License**. See the [LICENSE](LICENSE) file for more details.

---

## Contact

For questions or feedback, please open an issue in the GitHub repository.

---

DoxNet simplifies Verilog documentation, making it easier to maintain and share hardware designs! 🚀