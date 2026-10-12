from doxnet.cli import main


def test_empty_input_fails(tmp_path):
    rtl = tmp_path / 'rtl'
    rtl.mkdir()
    (rtl / 'empty.sv').write_text('// no design units')
    assert main(['-i', str(rtl), '-o', str(tmp_path / 'docs'), '--no-pdf', '--strict']) == 1


def test_invalid_coverage_fails(tmp_path):
    assert main(['-o', str(tmp_path / 'docs'), '--min-coverage', '105', '--no-pdf']) == 1


def test_invalid_language_in_config_fails(tmp_path):
    conf = tmp_path / 'config.json'
    conf.write_text('{"language":"xx","files":[]}')
    assert main(['-o', str(tmp_path / 'docs'), '--config', str(conf), '--no-pdf']) == 1
