"""Member documentation, body declarations, instances and hierarchy."""
import textwrap

from doxnet.hierarchy import link, walk
from doxnet.lexer import lex
from doxnet.model import Project
from doxnet.parser import parse_source


def parse(code, **kwargs):
    return parse_source(textwrap.dedent(code), "t.sv", **kwargs)


def test_trailing_and_leading_member_comments():
    units, diags = parse('''\
        /** @brief Adder */
        module add #(
          parameter int W = 8,   ///< Operand width
          /// Pipeline stages
          parameter int STAGES = 1
        ) (
          input  logic [W-1:0] a,  ///< First operand
          input  logic [W-1:0] b,  //!< Second operand
          /** Sum */
          output logic [W:0]   y
        );
          localparam int LAT = STAGES + 1;  ///< Total latency
        endmodule
        ''')
    assert diags == []
    unit = units[0]
    assert [(p.name, p.description) for p in unit.parameters] == [("W", "Operand width"), ("STAGES", "Pipeline stages")]
    assert [(p.name, p.description) for p in unit.ports] == [
        ("a", "First operand"), ("b", "Second operand"), ("y", "Sum")]
    assert unit.localparams[0].description == "Total latency"


def test_inline_and_header_documentation_conflict_is_reported():
    _, diags = parse('''\
        /** @brief x
         * @port a Also here */
        module m(input logic a /**< Here */); endmodule
        ''')
    assert [d.code for d in diags] == ["DOC003"]


def test_plain_trailing_comments_are_opt_in():
    code = '''\
        module m (
          // Clocks
          input  logic clk,  // System clock
          output logic q     // Result
        );
        endmodule
        '''
    assert [p.description for p in parse(code).units[0].ports] == ["", ""]
    ports = parse(code, plain_comments=True).units[0].ports
    assert [p.description for p in ports] == ["System clock", "Result"]


def test_struct_field_comments_do_not_leak_to_previous_member():
    units, diags = parse('''\
        package p;
          typedef logic [3:0] nib_t;  ///< A nibble
          typedef struct packed {
            logic a;  ///< Field a
          } s_t;
        endpackage
        ''')
    assert diags == []
    assert [(m.name, m.description) for m in units[0].members] == [("nib_t", "A nibble"), ("s_t", "")]


def test_body_parameters_and_header_localparams():
    units, _ = parse('''\
        module legacy(a); parameter W = 4; input [W-1:0] a; endmodule
        module modern #(parameter int W = 4, localparam int D = W * 2) (input logic a);
          parameter int X = 1;
        endmodule
        package p; parameter int Y = 3; endpackage
        ''')
    legacy, modern, pkg = units
    assert [(p.name, p.default) for p in legacy.parameters] == [("W", "4")]
    assert [(p.name, p.type) for p in legacy.ports] == [("a", "[W-1:0]")]
    assert [p.name for p in modern.parameters] == ["W"]
    assert [p.name for p in modern.localparams] == ["D", "X"]
    assert [p.name for p in pkg.localparams] == ["Y"]


def test_instances_with_overrides_arrays_and_multiple_names():
    units, _ = parse('''\
        module top;
          fifo #(.W(8), .D(16)) u_a (.clk(clk), .*), u_b (clk, rst);
          slice u_arr [3:0] (.x(x));
          and g1 (y, a, b);
          my_t sig;
          if (EN) begin : g_on
            leaf u_leaf ();
          end
          always_comb begin
            do_something(x);
          end
        endmodule
        ''')
    insts = units[0].instances
    assert [(i.module, i.name, i.array) for i in insts] == [
        ("fifo", "u_a", ""), ("fifo", "u_b", ""), ("slice", "u_arr", "[3:0]"), ("leaf", "u_leaf", "")]
    assert [(c.formal, c.actual) for c in insts[0].parameters] == [("W", "8"), ("D", "16")]
    assert [(c.formal, c.actual) for c in insts[0].connections] == [("clk", "clk"), ("*", "*")]
    assert [(c.formal, c.actual) for c in insts[1].connections] == [("", "clk"), ("", "rst")]


def test_assertions_and_functions_do_not_confuse_body_scan():
    units, diags = parse('''\
        module m(input logic clk, input logic a);
          property p_a; @(posedge clk) a; endproperty
          assert property (@(posedge clk) a) else $error("x");
          function automatic my_t f(input logic a); return a; endfunction
          sub u_sub(.a);
        endmodule
        ''')
    assert diags == []
    assert [i.name for i in units[0].instances] == ["u_sub"]
    assert [(m.kind, m.name) for m in units[0].members] == [("function", "f")]


def test_modports_typedefs_tasks_and_classes():
    units, _ = parse('''\
        interface bus_if(input logic clk);
          logic req, ack;
          /// Initiator view
          modport master(output req, input ack, import do_req),
                  slave(input req, output ack);  ///< Target view
          task automatic do_req(); req = 1; endtask
        endinterface
        package pkg;
          class item; int x; function new(); endfunction endclass
          typedef enum {A, B} e_t;
        endpackage
        ''')
    bus, pkg = units
    assert [(m.name, m.description) for m in bus.modports] == [("master", "Initiator view"), ("slave", "Target view")]
    assert [(p.direction, p.name) for p in bus.modports[0].ports] == [
        ("output", "req"), ("input", "ack"), ("import", "do_req")]
    assert [(m.kind, m.name) for m in bus.members] == [("task", "do_req")]
    assert [(m.kind, m.name) for m in pkg.members] == [("class", "item"), ("typedef", "e_t")]


def test_interface_ports_and_attributes():
    units, _ = parse('''\
        /** @brief c */
        (* keep_hierarchy *)
        module c((* mark *) input logic clk, bus_if.slave s, output logic o);
        endmodule
        ''')
    unit = units[0]
    assert unit.documented
    assert [(p.name, p.direction, p.type) for p in unit.ports] == [
        ("clk", "input", "logic"), ("s", "interface", "bus_if.slave"), ("o", "output", "logic")]


def test_unknown_and_empty_tags_are_reported():
    _, diags = parse('''\
        /** @brief x
         * @ouptut q typo
         * @port a
         */
        module m(input logic a); endmodule
        ''')
    assert sorted(d.code for d in diags) == ["DOC005", "DOC006"]


def test_file_comment_is_not_unit_documentation():
    result = parse('''\
        /** @file
         *  @brief Library of cells.
         */
        module cell; endmodule
        ''')
    assert result.file_doc.brief == "Library of cells."
    assert not result.units[0].documented
    assert result.diagnostics == []


def test_extern_and_class_declarations_at_top_level_are_skipped():
    units, diags = parse('''\
        extern module ext(input logic a);
        class c; virtual interface bus_if vif; endclass
        typedef class fwd;
        module real_one; endmodule
        ''')
    assert diags == []
    assert [u.name for u in units] == ["real_one"]


def test_end_labels_and_nested_modules():
    units, diags = parse('''\
        module outer;
          module inner; endmodule : inner
        endmodule : outer
        program automatic tb; endprogram
        ''')
    assert diags == []
    assert [(u.kind, u.name) for u in units] == [("module", "outer"), ("program", "tb")]


def test_hierarchy_resolution_and_interface_ports():
    units, _ = parse('''\
        interface bus_if(input logic clk); endinterface
        module leaf(bus_if b); endmodule
        module mid; leaf u_leaf(.b(x)); vendor_ip u_ip(); endmodule
        module top; mid u_mid(); mid u_mid2(); endmodule
        module unused; endmodule
        module top_dup; endmodule
        module top_dup; endmodule
        ''')
    project = Project("t", units=units, files=["t.sv"])
    link(project)
    leaf = project.unit("leaf")
    assert leaf.ports[0].direction == "interface"
    assert leaf.instantiated_by == ["mid"]
    assert project.unit("mid").instantiated_by == ["top"]
    assert [i.resolved for i in project.unit("mid").instances] == [True, False]
    assert project.top == ["top", "unused", "top_dup"]
    tree = [(depth, node.instance, node.module, node.resolved) for depth, node in walk(project.hierarchy[:1])]
    assert tree == [(0, "", "top", True), (1, "u_mid", "mid", True), (2, "u_leaf", "leaf", True),
                    (2, "u_ip", "vendor_ip", False), (1, "u_mid2", "mid", True),
                    (2, "u_leaf", "leaf", True), (2, "u_ip", "vendor_ip", False)]
    assert [d.code for d in project.diagnostics] == ["HDL002"]


def test_recursive_instantiation_terminates():
    units, _ = parse("module a; b u(); endmodule\nmodule b; a u(); endmodule\nmodule t; a x(); endmodule\n")
    project = Project("t", units=units, files=["t.sv"])
    link(project, top=["t"])
    nodes = list(walk(project.hierarchy))
    assert nodes[-1][1].recursive


def test_lexer_numbers_attributes_and_macros():
    tokens, _ = lex("assign x = 8'hFF + 'b1 + 1.5e3 + `WIDTH; (* keep *) wire w; @(*) y = 2'sd1;")
    kinds = {t.value: t.kind for t in tokens}
    assert kinds["8'hFF"] == "number"
    assert kinds["`WIDTH"] == "macro"
    assert "keep" not in kinds
    assert kinds["2'sd1"] == "number"


def test_comment_attaches_across_directives_and_plain_comments():
    units, diags = parse('''\
        /** @brief Arbiter */
        `timescale 1ns/1ps
        // lint_off UNUSED
        module arbiter; endmodule
        /** @brief Not attached */
        import pkg::*;
        module other; endmodule
        ''')
    assert [u.documented for u in units] == [True, False]
    assert [d.code for d in diags] == ["DOC004"]
