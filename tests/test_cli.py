import json
from pathlib import Path
import sys

import pytest

from doxnet.cli import main

EXAMPLE = '''\
/**
 * @brief A configurable device
 * @parameter WIDTH Bus width
 * @input clk Clock
 * @output ready Ready state
 */
module device #(parameter int WIDTH = 8) (
 input logic clk,
 output logic ready
);
endmodule
'''


def _project(tmp_path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "device.sv").write_text(EXAMPLE, encoding="utf-8")
    return rtl, tmp_path / "output"


def test_end_to_end_three_formats_and_gates(tmp_path):
    rtl, dest = _project(tmp_path)
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--strict",
                 "--min-port-coverage", "100", "--min-parameter-coverage", "100"]) == 0
    report = json.loads((dest / "documentation.json").read_text())
    assert report["coverage"]["ports"]["percent"] == 100
    assert report["units"][0]["parameters"][0]["default"] == "8"
    assert "device" in (dest / "documentation.html").read_text(encoding="utf-8")
    assert "Ports" in (dest / "documentation.md").read_text()


def test_invalid_config_language_is_input_error(tmp_path):
    _, dest = _project(tmp_path)
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"language": "invalid", "files": ["rtl/device.sv"]}))
    assert main(["-o", str(dest), "--config", str(config), "--no-pdf"]) == 1
    assert not dest.exists()


def test_config_order_and_cli_override(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "second.sv").write_text("package second; endpackage")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"title": "From JSON", "language": "de",
                                  "files": ["rtl/second.sv", "rtl/device.sv"]}))
    assert main(["-o", str(dest), "--config", str(config), "--title", "From CLI", "--no-pdf"]) == 0
    doc = (dest / "documentation.md").read_text()
    assert "From CLI" in doc
    assert doc.index("second.sv") < doc.index("device.sv")
    assert "Parameter" in doc  # German translation


def test_filelist_nested(tmp_path):
    _, dest = _project(tmp_path)
    inner = tmp_path / "inner.f"
    inner.write_text("rtl/device.sv\n")
    outer = tmp_path / "list.f"
    outer.write_text("# comment\n-f inner.f\n")
    assert main(["-o", str(dest), "--filelist", str(outer), "--no-pdf"]) == 0


def test_unsupported_filelist_directive_is_error(tmp_path):
    _, dest = _project(tmp_path)
    filelist = tmp_path / "list.f"
    filelist.write_text("-y lib\nrtl/device.sv\n")
    assert main(["-o", str(dest), "--filelist", str(filelist)]) == 1


def test_empty_input_and_bad_gates(tmp_path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "empty.sv").write_text("// no modules")
    dest = tmp_path / "docs"
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--strict"]) == 1
    assert main(["-i", str(rtl), "-o", str(dest), "--min-coverage", "101"]) == 1
    assert not dest.exists()


def test_undocumented_units_and_port_coverage_gate(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "undoc.sv").write_text("module missing(input logic a); endmodule")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--strict"]) == 2
    doc = (dest / "documentation.md").read_text()
    assert "Undocumented" in doc
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--min-port-coverage", "100"]) == 2


def test_stale_annotations_fail_on_warnings(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "device.sv").write_text('/** @brief hi\n * @port doesnt_exist Not real\n */\nmodule m; endmodule')
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--fail-on-warnings"]) == 3


def test_output_traversal_and_conflict_rejected(tmp_path):
    rtl, dest = _project(tmp_path)
    assert main(["-i", str(rtl), "-o", str(dest), "--html-file", "../escape.html"]) == 1
    assert main(["-i", str(rtl), "-o", str(dest), "--html-file", "documentation.md"]) == 1


def test_exclusions_are_effective(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "other.sv").write_text('module other; endmodule')
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--strict",
                 "--exclude", "other.sv"]) == 0
    data = json.loads((dest / "documentation.json").read_text())
    assert len(data["units"]) == 1


def test_invalid_hdl_syntax_fails_without_writing_docs(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "device.sv").write_text("/** @brief wrong */\nmodule incomplete(input logic clk);")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf"]) == 1
    assert not dest.exists()


def test_comment_with_unknown_port_fails_warning_gate(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "device.sv").write_text("/** @brief hi\n * @port missing Unrecognized\n */\nmodule m; endmodule")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--fail-on-warnings"]) == 3
    report = json.loads((dest / "documentation.json").read_text())
    assert report["diagnostics"][0]["code"] == "DOC001"


def test_orphan_doxygen_comment_is_warning(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "device.sv").write_text("/** @brief orphan */\nint unrelated;\nmodule m; endmodule")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--fail-on-warnings"]) == 3


def test_missing_ports_cannot_report_full_coverage(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "device.sv").write_text("/** @brief no ports */\npackage p; endpackage")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--min-port-coverage", "100"]) == 2
    report = json.loads((dest / "documentation.json").read_text())
    assert report["coverage"]["ports"]["percent"] is None


def test_source_url_invalid_credentials_or_fragment(tmp_path):
    rtl, dest = _project(tmp_path)
    for url in ("javascript:alert(1)", "https://user:pw@example.com/path", "https://example.com/#frag"):
        assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf", "--source-url", url]) == 1
    assert not dest.exists()


def test_pdf_failure_explicitly_required_is_error(tmp_path, monkeypatch):
    rtl, dest = _project(tmp_path)
    monkeypatch.setattr("doxnet.cli.convert_md_to_pdf", lambda *args: False)
    assert main(["-i", str(rtl), "-o", str(dest), "--pdf-required"]) == 3
    assert (dest / "documentation.md").is_file()


def test_opt_out_of_source_embedding(tmp_path):
    rtl, dest = _project(tmp_path)
    assert main(["-i", str(rtl), "-o", str(dest), "--no-source", "--no-pdf"]) == 0
    html = (dest / "documentation.html").read_text(encoding="utf-8")
    assert 'class="source"' not in html


def test_symlink_outside_input_is_not_read_implicitly(tmp_path):
    rtl, dest = _project(tmp_path)
    secret = tmp_path / "secret.sv"
    secret.write_text("module secret; endmodule")
    try:
        (rtl / "external.sv").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf"]) == 1
    assert not dest.exists()


ROOT = Path(__file__).resolve().parent.parent


def test_example_project_passes_all_gates(tmp_path):
    dest = tmp_path / "out"
    assert main(["-c", str(ROOT / "examples" / "doxnet.json"), "-o", str(dest), "--no-pdf"]) == 0
    report = json.loads((dest / "documentation.json").read_text(encoding="utf-8"))
    assert report["top"] == ["uart_top"]
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((ROOT / "docs" / "schema" / "doxnet.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    html = (dest / "index.html").read_text(encoding="utf-8")
    assert 'class="block-diagram"' in html
    assert 'class="tree"' in html


def test_defines_select_ifdef_branches(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "opt.sv").write_text("`ifdef WITH_OPT\n/** @brief opt */\nmodule opt; endmodule\n`endif\n")
    assert main(["-i", str(rtl), "-o", str(dest), "--formats", "json"]) == 0
    names = [u["name"] for u in json.loads((dest / "documentation.json").read_text())["units"]]
    assert names == ["device"]
    assert main(["-i", str(rtl), "-o", str(dest), "--formats", "json", "-D", "WITH_OPT"]) == 0
    names = [u["name"] for u in json.loads((dest / "documentation.json").read_text())["units"]]
    assert names == ["device", "opt"]
    assert not (dest / "documentation.html").exists()


def test_check_mode_writes_nothing(tmp_path):
    rtl, dest = _project(tmp_path)
    assert main(["-i", str(rtl), "--check", "--strict"]) == 0
    assert main(["-i", str(rtl)]) == 1  # neither --output nor --check


def test_github_annotations_and_disable(tmp_path, capsys, monkeypatch):
    rtl, dest = _project(tmp_path)
    (rtl / "orphan.sv").write_text("/** @brief orphan */\nint x;\nmodule m; endmodule\n")
    monkeypatch.chdir(tmp_path)
    assert main(["-i", str(rtl), "--check", "--diagnostics-format", "github"]) == 0
    assert "::warning file=rtl/orphan.sv,line=1,title=DOC004::" in capsys.readouterr().out
    assert main(["-i", str(rtl), "--check", "--fail-on-warnings", "--disable", "DOC004"]) == 0


def test_toml_config_and_unknown_keys(tmp_path):
    rtl, dest = _project(tmp_path)
    if sys.version_info < (3, 11):
        pytest.importorskip("tomli")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doxnet]\ntitle = "From TOML"\ninput = "rtl"\nformats = ["markdown"]\nstrict = true\n')
    assert main(["-c", str(tmp_path / "pyproject.toml"), "-o", str(dest)]) == 0
    assert "From TOML" in (dest / "documentation.md").read_text()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"input": "rtl", "min_coverag": 50}))
    assert main(["-c", str(bad), "-o", str(dest)]) == 1


def test_filelist_defines_incdirs_and_env(tmp_path, monkeypatch):
    rtl, dest = _project(tmp_path)
    (tmp_path / "inc").mkdir()
    (tmp_path / "inc" / "cfg.svh").write_text("`define FROM_HEADER\n")
    (rtl / "extra.sv").write_text(
        '`include "cfg.svh"\n`ifdef FROM_HEADER\n`ifdef FROM_LIST\nmodule extra; endmodule\n`endif\n`endif\n')
    monkeypatch.setenv("RTL_ROOT", str(rtl))
    filelist = tmp_path / "files.f"
    filelist.write_text("+incdir+inc\n+define+FROM_LIST=1\n$RTL_ROOT/device.sv  // main\n${RTL_ROOT}/extra.sv\n")
    assert main(["-f", str(filelist), "-o", str(dest), "--formats", "json"]) == 0
    names = [u["name"] for u in json.loads((dest / "documentation.json").read_text())["units"]]
    assert names == ["device", "extra"]
    filelist.write_text("$UNSET_VARIABLE_FOR_TEST/device.sv\n")
    assert main(["-f", str(filelist), "-o", str(dest)]) == 1


def test_preprocessor_errors_stop_generation(tmp_path):
    rtl, dest = _project(tmp_path)
    (rtl / "broken.sv").write_text("`ifdef A\nmodule x; endmodule\n")
    assert main(["-i", str(rtl), "-o", str(dest)]) == 1
    assert not dest.exists()
    assert main(["-i", str(rtl), "-o", str(dest), "--no-preprocess", "--formats", "json"]) == 0


def test_python_dash_m_entry_point(tmp_path):
    import subprocess
    result = subprocess.run([sys.executable, "-m", "doxnet", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.startswith("doxnet ")
