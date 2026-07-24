"""Unit tests for the Mako-compiled-source patchers in the mypy_mako linter."""

import pytest

from middlewared.test.linter.mypy_mako import patches


def test_deshadow_blanks_builtin_shadow_line():
    # Mako's `list = context.get('list', UNDEFINED)` no-op is blanked so a natural
    # `list[str]` annotation in the template resolves to the real builtin.
    code = "    list = context.get('list', UNDEFINED)\n"
    assert patches.deshadow_builtins(code) == "\n"


@pytest.mark.parametrize("name", ["list", "dict", "str", "int", "bool", "set", "sorted", "filter", "map"])
def test_deshadow_blanks_every_builtin(name):
    code = f"    {name} = context.get('{name}', UNDEFINED)\n"
    assert patches.deshadow_builtins(code) == "\n"


def test_deshadow_leaves_non_builtin_context_vars_untouched():
    # Real template locals must keep their `context.get` binding.
    code = "    render_ctx = context.get('render_ctx', UNDEFINED)\n    targets = context.get('targets', UNDEFINED)\n"
    assert patches.deshadow_builtins(code) == code


def test_deshadow_only_matches_the_self_rebind_shape():
    # A `context.get` whose key differs from the LHS is not Mako's shadow no-op.
    code = "    basename = context.get('iscsi.global.config', UNDEFINED)\n"
    assert patches.deshadow_builtins(code) == code


def test_deshadow_preserves_line_count():
    # The line map depends on line numbering being preserved across patching.
    code = (
        "def render_body(context, **pageargs):\n"
        "    list = context.get('list', UNDEFINED)\n"
        "    render_ctx = context.get('render_ctx', UNDEFINED)\n"
        "    return ''\n"
    )
    patched = patches.deshadow_builtins(code)
    assert patched.count("\n") == code.count("\n")
    assert "list = context.get" not in patched
    assert "render_ctx = context.get('render_ctx', UNDEFINED)" in patched


def test_deshadow_registered_in_pipeline():
    # patch() must actually run the deshadow pass.
    code = "    dict = context.get('dict', UNDEFINED)\n"
    assert "dict = context.get" not in patches.patch(code)


def test_render_def_annotates_module_level_def():
    code = "def render_security_headers(context,indent=8):\n"
    patched = patches.annotate_render_defs(code)
    assert patched == "def render_security_headers(context: runtime.Context, indent: int = 8) -> str:\n"


def test_render_def_annotates_nested_wrapper():
    # The `${foo()}` call sites hit this wrapper, so it must be typed too.
    code = (
        "        def security_headers(indent=8):\n"
        "            return render_security_headers(context._locals(__M_locals),indent)\n"
    )
    patched = patches.annotate_render_defs(code)
    assert "def security_headers(indent: int = 8) -> str:" in patched
    # Body (the render_ call) is preserved untouched.
    assert "return render_security_headers(context._locals(__M_locals),indent)" in patched


def test_render_def_leaves_render_body_to_scaffolding():
    code = "def render_body(context,**pageargs):\n"
    assert patches.annotate_render_defs(code) == code


def test_render_def_bails_when_an_arg_has_no_default():
    # `target_id` has no default, so its type is unknowable -> leave the def untouched
    # rather than emit a still-untyped (and now inconsistent) signature.
    code = "def render_retrieve_luns(context,target_id,spacing=''):\n"
    assert patches.annotate_render_defs(code) == code


def test_render_def_infers_literal_types():
    code = "def render_x(context,flag=True,count=3,label='hi'):\n"
    patched = patches.annotate_render_defs(code)
    assert patched == (
        "def render_x(context: runtime.Context, flag: bool = True, count: int = 3, label: str = 'hi') -> str:\n"
    )


def test_render_def_registered_in_pipeline():
    code = "def render_security_headers(context,indent=8):\n"
    assert "-> str:" in patches.patch(code)
