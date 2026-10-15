from doxnet.comments import parse_comment


def test_tags_continue_until_blank_line():
    doc = parse_comment("""/**
 * @brief Short
 *   continued brief.
 *
 * First paragraph
 * still first.
 *
 * Second paragraph.
 * @port clk Clock input that
 *   spans two lines.
 */""")
    assert doc.brief == "Short continued brief."
    assert doc.paragraphs == ["First paragraph\nstill first.", "Second paragraph."]
    assert doc.entries[0].name == "clk"
    assert doc.entries[0].text == "Clock input that spans two lines."


def test_autobrief_uses_first_paragraph():
    doc = parse_comment("/** Adds two numbers.\n *\n * Saturates on overflow. */").autobrief()
    assert doc.brief == "Adds two numbers."
    assert doc.description == "Saturates on overflow."


def test_metadata_lists_and_deprecated():
    doc = parse_comment("""/**
 * @author A. Person
 * @version 2.0
 * @since 1.1
 * @note First note.
 * @warning Careful.
 * @todo Finish.
 * @see other_module
 * @deprecated Use new_thing.
 */""")
    assert doc.metadata == {"author": "A. Person", "version": "2.0", "since": "1.1"}
    assert doc.lists["notes"] == ["First note."]
    assert doc.lists["warnings"] == ["Careful."]
    assert doc.lists["todos"] == ["Finish."]
    assert doc.lists["see"] == ["other_module"]
    assert doc.deprecated == "Use new_thing."


def test_backslash_tags_direction_hints_and_separators():
    doc = parse_comment("/// \\brief Hello\n/// @param[in] a - first\n/// @param[out] b: second")
    assert doc.brief == "Hello"
    assert [(e.tag, e.name, e.text, e.direction) for e in doc.entries] == [
        ("param", "a", "first", "input"), ("param", "b", "second", "output")]


def test_unknown_tags_are_recorded():
    doc = parse_comment("/** @brief x\n * @ouptut y typo */", first_line=10)
    assert doc.unknown_tags == [("ouptut", 11)]


def test_relative_indentation_is_kept_for_markdown_lists():
    doc = parse_comment("/**\n * Steps:\n * - one\n *   - nested\n */")
    assert doc.description == "Steps:\n- one\n  - nested"


def test_file_comment_flag():
    assert parse_comment("/** @file\n * @brief Top */").is_file
