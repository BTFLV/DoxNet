import textwrap

from doxnet.parser import parse_doxygen_comment, parse_verilog_file, remove_doxnet_comments


SAMPLE = textwrap.dedent(
    """\
    /**
     * @brief A simple example module.
     *
     * @parameter WIDTH Bit width of data bus.
     * @input clk Clock signal.
     * @output ready Ready flag.
     */
    module example #(parameter WIDTH = 8) (
      input  wire clk,
      output wire ready
    );
    endmodule

    interface undocumented_bus;
    endinterface
    """
)


def test_parse_doxygen_comment_extracts_fields():
    lines = SAMPLE.splitlines()[:7]
    info = parse_doxygen_comment(lines)
    assert info["brief"] == "A simple example module."
    assert info["parameters"] == ["WIDTH Bit width of data bus."]
    assert info["inputs"] == ["clk Clock signal."]
    assert info["outputs"] == ["ready Ready flag."]


def test_parse_verilog_file_reports_coverage(tmp_path):
    f = tmp_path / "example.sv"
    f.write_text(SAMPLE, encoding="utf-8")

    docs, (documented, total, undocumented) = parse_verilog_file(str(f))

    assert len(docs) == 1
    assert docs[0]["module"] == "example"
    assert docs[0]["unit_kind"] == "module"
    assert total == 2
    assert documented == 1
    assert undocumented == ["undocumented_bus"]


def test_remove_doxnet_comments_strips_blocks():
    code = "/** @brief x */\nmodule m;\nendmodule\n"
    cleaned = remove_doxnet_comments(code)
    assert "@brief" not in cleaned
    assert "module m;" in cleaned
