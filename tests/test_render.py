import json

from doxnet.model import DesignUnit, Port, Project
from doxnet.render import render_html, render_json, render_markdown


def _project():
    return Project(title='<img src=x onerror=alert(1)>', files=['src/demo.sv'], units=[
        DesignUnit(kind='module', name='demo', file='src/demo.sv', line=2, end_line=5,
                   brief='<script>alert(1)</script> **demonstration**', documented=True,
                   ports=[Port(name='clk', direction='input', type='logic',
                               description='[attack](javascript:alert(1))')])])


def test_untrusted_html_and_js_urls_not_executable():
    project = _project()
    html = render_html(project, {'src/demo.sv': 'module demo(input logic clk); endmodule'}, source_url='https://github.com/a/b/blob/main')
    assert '<script>alert(1)</script>' not in html
    assert '<img src=x onerror=alert(1)>' not in html
    assert 'href="javascript:' not in html
    assert 'https://github.com/a/b/blob/main/src/demo.sv#L2' in html
    assert 'id="search"' in html


def test_markdown_source_fence_cannot_break_early():
    code = 'module m;\n  string s="```";\nendmodule\n'
    md = render_markdown(_project(), {'src/demo.sv': code})
    assert '````systemverilog' in md
    assert code.strip() in md
    assert '&lt;img' in md


def test_json_and_empty_coverage_metric():
    project = Project(title='Empty', files=['empty.sv'])
    parsed = json.loads(render_json(project))
    assert parsed['coverage']['units']['percent'] is None
    assert parsed['schema_version'] == 2
    assert parsed['generator']['name'] == 'doxnet'


def test_search_handles_filename_and_escaped_values():
    project = _project()
    html = render_html(project, {'src/demo.sv': 'module demo;endmodule'})
    assert 'data-search="module demo src/demo.sv' in html
    assert '<img src=x onerror=alert(1)>' not in html
    assert 'id="unit-src-demo-sv-module-demo-2"' in html


def test_renderer_localized_labels():
    project = _project()
    md = render_markdown(project, {}, language="de", include_source=False)
    html = render_html(project, {}, language="de", include_source=False)
    assert "Dateien" in md
    assert "Richtung" in md
    assert 'lang="de"' in html
