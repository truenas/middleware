import pytest

from middlewared.api.base.server.doc import expand_method_refs, reflow_docstring


@pytest.mark.parametrize(
    "doc,expected",
    [
        # A bare reference expands to a :doc: link whose text is the method name and
        # whose target is the api_methods_ page for that method.
        (
            ":method:`core.bulk`",
            ":doc:`core.bulk <api_methods_core.bulk>`",
        ),
        # Dotted, multi-segment method names are preserved in both text and target.
        (
            ":method:`zfs.resource.snapshot.destroy`",
            ":doc:`zfs.resource.snapshot.destroy <api_methods_zfs.resource.snapshot.destroy>`",
        ),
        # References are expanded inline, leaving surrounding prose untouched.
        (
            "To destroy snapshots, use :method:`zfs.resource.snapshot.destroy` instead.",
            "To destroy snapshots, use "
            ":doc:`zfs.resource.snapshot.destroy <api_methods_zfs.resource.snapshot.destroy>` instead.",
        ),
        # Multiple references on the same line are each expanded.
        (
            ":method:`interface.create` then :method:`interface.commit`",
            ":doc:`interface.create <api_methods_interface.create>` then "
            ":doc:`interface.commit <api_methods_interface.commit>`",
        ),
        # Text without a reference is returned unchanged.
        (
            "No references here.",
            "No references here.",
        ),
    ],
)
def test_expand_method_refs(doc, expected):
    assert expand_method_refs(doc) == expected


def test_reflow_docstring_expands_method_refs():
    # reflow_docstring runs the expansion as part of preprocessing, so :method:
    # shorthand in a hard-wrapped paragraph is both expanded and unwrapped.
    doc = "See :method:`core.bulk`\nfor details."
    assert reflow_docstring(doc) == "See :doc:`core.bulk <api_methods_core.bulk>` for details."
