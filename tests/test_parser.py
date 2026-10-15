"""Parser regressions and public compatibility API tests."""
import textwrap

from doxnet.parser import (
    find_all_units,
    parse_doxygen_comment,
    parse_source,
    parse_verilog_file,
    remove_doxnet_comments,
)

SAMPLE = textwrap.dedent('''\
/**
 * @brief A simple example module.
 * @parameter WIDTH Bus width.
 * @input clk Clock signal.
 * @output ready Ready flag.
 */
module example #(parameter int WIDTH = 8) (
  input logic clk,
  output logic ready
);
  localparam int DEPTH = 16;
endmodule
interface undocumented_bus;
endinterface
''')


def test_legacy_comment_fields():
    comment = parse_doxygen_comment(SAMPLE.splitlines()[:6])
    assert comment["brief"] == "A simple example module."
    assert comment["inputs"] == ["clk Clock signal."]
    assert comment["parameters"] == ["WIDTH Bus width."]


def test_legacy_file_coverage(tmp_path):
    path = tmp_path / "example.sv"
    path.write_text(SAMPLE)
    docs, counts = parse_verilog_file(path)
    assert len(docs) == 1
    assert docs[0]["module"] == "example"
    assert counts == (1, 2, ["undocumented_bus"])


def test_automatic_interface_extraction():
    units, diagnostics = parse_source(SAMPLE, "example.sv")
    assert not diagnostics
    assert [u.kind for u in units] == ["module", "interface"]
    assert [(p.name, p.direction, p.description) for p in units[0].ports] == [
        ("clk", "input", "Clock signal."), ("ready", "output", "Ready flag.")]
    assert [(p.name, p.type, p.default) for p in units[0].parameters] == [("WIDTH", "int", "8")]
    assert [(p.name, p.default) for p in units[0].localparams] == [("DEPTH", "16")]


def test_keywords_in_strings_and_comments_not_counted():
    code = '''\
// module in_comment;
`define BAD_MODULE module from_macro
module real;
  string label = "module phantom; /* package fake */";
  /* interface fake; */
endmodule
'''
    units, _ = parse_source(code)
    assert [(u.kind, u.name) for u in units] == [("module", "real")]
    assert find_all_units(code.splitlines(keepends=True)) == [("module", "real", 2)]


def test_multiline_and_lifetime_and_inherited_ansi_ports():
    code = '''\
/** @brief Dual port memory */
module automatic memory
#(
    parameter int WIDTH = 8,
    DEPTH = 32
)
(
    input logic [WIDTH-1:0] data_i, data2_i,
    output logic ready_o
);
endmodule
'''
    units, warnings = parse_source(code)
    assert not warnings
    assert len(units) == 1
    assert units[0].name == "memory"
    assert [(p.name, p.direction, p.type) for p in units[0].ports] == [
        ("data_i", "input", "logic [WIDTH-1:0]"),
        ("data2_i", "input", "logic [WIDTH-1:0]"),
        ("ready_o", "output", "logic"),
    ]
    assert [(p.name, p.type, p.default) for p in units[0].parameters] == [
        ("WIDTH", "int", "8"), ("DEPTH", "int", "32")]


def test_nonansi_ports_resolved_from_body():
    units, _ = parse_source('module old_style(a,b); input wire a, b; endmodule')
    assert [(p.name, p.direction, p.type) for p in units[0].ports] == [
        ("a", "input", "wire"), ("b", "input", "wire")]


def test_doxygen_attaches_only_to_adjacent_design_unit():
    code = '''\
/** @brief Not a module */
int unrelated;
module no_docs; endmodule
/** @brief Correct */
interface bus; endinterface
'''
    units, _ = parse_source(code)
    assert not units[0].documented
    assert units[1].documented
    assert units[1].brief == "Correct"


def test_stale_duplicate_and_direction_diagnostics():
    code = '''\
/**
 * @brief Example
 * @input ready Not an input
 * @output ready Duplicate
 * @port nonexistent Never existed
 */
module m(output logic ready); endmodule
'''
    units, warnings = parse_source(code)
    assert units[0].documented
    assert {w.code for w in warnings} == {"DOC001", "DOC002", "DOC003"}


def test_slash_comments_and_removal_preserves_non_doc_text():
    code = '/// @brief Example\n/// @input clk Clock\nmodule m(input clk);\n"/** not a comment */";\nendmodule\n'
    units, _ = parse_source(code)
    assert units[0].brief == "Example"
    assert units[0].ports[0].description == "Clock"
    stripped = remove_doxnet_comments(code)
    assert "@brief" not in stripped
    assert '"/** not a comment */"' in stripped


def test_param_expression_commas_do_not_split():
    code = 'module m #(parameter int W = f(1,2), D = 4) (input logic [W-1:0] a); endmodule'
    units, _ = parse_source(code)
    assert [(p.name, p.default) for p in units[0].parameters] == [("W", "f(1,2)"), ("D", "4")]


def test_empty_comment_not_documented():
    units, _ = parse_source('/** */\npackage p; endpackage')
    assert not units[0].documented


def test_module_header_package_import_before_parameter_list():
    code = '''\
/** @brief A device */
module device import bus_pkg::*;
    #(parameter int WIDTH = 16)
    (input logic [WIDTH-1:0] payload, output logic ready);
endmodule
'''
    units, diagnostics = parse_source(code)
    assert diagnostics == []
    assert [(x.name, x.default) for x in units[0].parameters] == [("WIDTH", "16")]
    assert [(x.name, x.direction) for x in units[0].ports] == [("payload", "input"), ("ready", "output")]


def test_bang_doxygen_comment_is_documentation():
    units, diagnostics = parse_source("/*! @brief Hello */\npackage example; endpackage")
    assert not diagnostics
    assert units[0].brief == "Hello"
    assert units[0].documented


def test_orphan_tag_is_diagnostic_not_attached_to_next_unit():
    code = '''\
/** @brief Not attached */
int unrelated;
module no_docs; endmodule
'''
    units, diagnostics = parse_source(code)
    assert len(units) == 1
    assert not units[0].documented
    assert [(d.code, d.line) for d in diagnostics] == [("DOC004", 1)]


def test_missing_endmodule_is_parse_error():
    units, diagnostics = parse_source("/** @brief hello */\nmodule incomplete(input logic clk);")
    assert units == []
    assert [(d.code, d.severity) for d in diagnostics] == [("HDL001", "error"), ("DOC004", "warning")]


def test_unclosed_header_parenthesis_is_parse_error():
    units, diagnostics = parse_source("module bad #(parameter int W = 8;")
    assert units == []
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "HDL001"


def test_multiple_design_units_are_extracted_in_order():
    code = '''\
/** @brief alpha */
package alpha; endpackage
// non-doc comment
/** @brief beta */
interface beta(input logic clock); endinterface
module gamma; string name = "endmodule module ghost"; endmodule
'''
    units, diagnostics = parse_source(code)
    assert not diagnostics
    assert [(u.kind, u.name) for u in units] == [
        ("package", "alpha"), ("interface", "beta"), ("module", "gamma")]
    assert [u.documented for u in units] == [True, True, False]


def test_parameter_defaults_keep_nested_commas_and_typedefs():
    source = "module m #(parameter type T=logic [7:0], parameter int N=f(1,2)) (input T value); endmodule"
    units, diagnostics = parse_source(source)
    assert diagnostics == []
    assert [(p.name, p.default) for p in units[0].parameters] == [
        ("T", "logic [7:0]"), ("N", "f(1,2)")]
    assert [(p.name, p.type) for p in units[0].ports] == [("value", "T")]
