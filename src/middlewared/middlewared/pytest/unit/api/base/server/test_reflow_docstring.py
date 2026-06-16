import pytest

from middlewared.api.base.server.doc import reflow_docstring


@pytest.mark.parametrize("doc,expected", [
    # Plain prose hard-wrapped across lines is unwrapped into a single line so it
    # reflows when rendered as HTML.
    (
        "Returns a list of things\nthat spans several lines.",
        "Returns a list of things that spans several lines.",
    ),
    # Blank-line-separated paragraphs stay separate; each is unwrapped on its own.
    (
        "First paragraph\nwrapped.\n\nSecond paragraph.",
        "First paragraph wrapped.\n\nSecond paragraph.",
    ),
    # A ``::`` paragraph opens a literal block: the following indented run is kept
    # verbatim (indentation and line breaks preserved) instead of being unwrapped.
    (
        'Example output::\n\n    [\n        {"a": 1}\n    ]',
        'Example output::\n\n    [\n        {"a": 1}\n    ]',
    ),
    # A literal block may span several blank-line-separated sub-blocks; each indented
    # block is preserved.
    (
        "Fields::\n\n    a: first\n\n    b: second",
        "Fields::\n\n    a: first\n\n    b: second",
    ),
    # The literal block ends when the text dedents; trailing prose is unwrapped.
    (
        "Example::\n\n    code()\n\nTrailing prose\nthat wraps.",
        "Example::\n\n    code()\n\nTrailing prose that wraps.",
    ),
    # Indentation is preserved even without a ``::`` marker, so block quotes, tables,
    # and similar constructs survive rather than being mangled into prose.
    (
        "See below:\n\n    quoted text\n    second line",
        "See below:\n\n    quoted text\n    second line",
    ),
    # A list with wrapped (indented) continuation lines keeps its structure and is
    # not flattened into a single run-on line.
    (
        "- item one\n  continued\n- item two",
        "- item one\n  continued\n- item two",
    ),
    # Directive blocks and their indented bodies are preserved verbatim.
    (
        ".. note::\n\n    Body of the note\n    wraps here.",
        ".. note::\n\n    Body of the note\n    wraps here.",
    ),
    # A top-level list with no continuation lines is preserved (not joined into prose).
    (
        "Options:\n\n- one\n- two",
        "Options:\n\n- one\n- two",
    ),
    # Leading and trailing blank lines are stripped.
    (
        "\n\nHello there\nworld.\n\n",
        "Hello there world.",
    ),
])
def test_reflow_docstring(doc, expected):
    assert reflow_docstring(doc) == expected
