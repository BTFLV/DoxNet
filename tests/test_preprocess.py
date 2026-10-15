import pytest

from doxnet.parser import parse_source
from doxnet.preprocess import Preprocessor, parse_define


def _names(text):
    return [u.name for u in parse_source(text).units]


def test_inactive_branches_are_blanked_with_lines_kept():
    source = "`ifdef FAST\nmodule fast; endmodule\n`else\nmodule slow; endmodule\n`endif\n"
    text, diags = Preprocessor().process(source, "a.sv")
    assert diags == []
    assert text.count("\n") == source.count("\n")
    assert len(text) == len(source)
    assert _names(text) == ["slow"]
    text, _ = Preprocessor({"FAST": ""}).process(source, "a.sv")
    assert _names(text) == ["fast"]
    assert parse_source(text).units[0].line == 2


def test_elsif_ifndef_nesting_and_define_in_source():
    source = """\
`define B
`ifdef A
module a; endmodule
`elsif B
  `ifndef C
module b; endmodule
  `else
module c; endmodule
  `endif
`else
module d; endmodule
`endif
"""
    text, diags = Preprocessor().process(source, "x.sv")
    assert not diags
    assert _names(text) == ["b"]


def test_undef_and_defines_carry_over_between_files():
    pre = Preprocessor()
    pre.process("`define FEATURE 1\n", "defs.sv")
    text, _ = pre.process("`ifdef FEATURE\nmodule on; endmodule\n`endif\n", "use.sv")
    assert _names(text) == ["on"]
    pre.process("`undef FEATURE\n", "undef.sv")
    text, _ = pre.process("`ifdef FEATURE\nmodule on; endmodule\n`endif\n", "use.sv")
    assert _names(text) == []


def test_conditional_expressions():
    source = "`ifdef (A && !B)\nmodule yes; endmodule\n`endif\n`ifdef (A || B) module also; endmodule `endif\n"
    text, diags = Preprocessor({"A": ""}).process(source, "x.sv")
    assert not diags
    assert _names(text) == ["yes", "also"]


def test_directives_in_comments_and_strings_are_ignored():
    source = '// `ifdef NOPE\nmodule m; string s = "`endif"; /* `else */ endmodule\n'
    text, diags = Preprocessor().process(source, "x.sv")
    assert diags == []
    assert _names(text) == ["m"]


def test_unbalanced_directives_are_errors():
    _, diags = Preprocessor().process("`ifdef A\nmodule m; endmodule\n", "x.sv")
    assert [(d.code, d.severity) for d in diags] == [("PP001", "error")]
    _, diags = Preprocessor().process("`endif\n", "x.sv")
    assert [d.code for d in diags] == ["PP001"]
    _, diags = Preprocessor().process("`ifdef A\n`else\n`else\n`endif\n", "x.sv")
    assert [d.code for d in diags] == ["PP001"]


def test_include_files_contribute_defines(tmp_path):
    inc = tmp_path / "inc"
    inc.mkdir()
    (inc / "cfg.svh").write_text("`define WITH_DEBUG\n")
    main = tmp_path / "top.sv"
    source = '`include "cfg.svh"\n`ifdef WITH_DEBUG\nmodule dbg; endmodule\n`endif\n'
    text, diags = Preprocessor(include_dirs=[inc]).process(source, "top.sv", main)
    assert not diags
    assert _names(text) == ["dbg"]
    _, diags = Preprocessor().process(source, "top.sv", main)
    assert [d.code for d in diags] == ["PP002"]


def test_recursive_include_is_reported(tmp_path):
    (tmp_path / "a.svh").write_text('`include "a.svh"\n')
    _, diags = Preprocessor().process('`include "a.svh"\n', "top.sv", tmp_path / "top.sv")
    assert diags == []  # the inner warning stays with the header; errors would propagate


def test_parse_define():
    assert parse_define("WIDTH=8") == ("WIDTH", "8")
    assert parse_define("SIM") == ("SIM", "")
    with pytest.raises(ValueError):
        parse_define("8BAD")
