import json

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
    filelist.write_text("+define+FEATURE\n")
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
    import pytest
    rtl, dest = _project(tmp_path)
    secret = tmp_path / "secret.sv"
    secret.write_text("module secret; endmodule")
    try:
        (rtl / "external.sv").symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this platform")
    assert main(["-i", str(rtl), "-o", str(dest), "--no-pdf"]) == 1
    assert not dest.exists()
