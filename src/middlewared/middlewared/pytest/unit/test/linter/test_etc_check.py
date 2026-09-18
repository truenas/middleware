"""Unit tests for the etc_files renderer checker."""

import ast
import os

from mako.template import Template
import pytest

from middlewared.plugins.etc import EtcService, RendererType
from middlewared.test.linter import etc_check


def compile_body(body: str) -> ast.Module:
    return ast.parse(Template(f"<%\n{body}%>\\\n").code)


def problems(body: str) -> list[str]:
    found = []
    for node in etc_check.iter_imports(compile_body(body)):
        found.extend(etc_check.resolve_import(node))

    return found


def test_every_renderer_is_clean():
    found = []
    for path in etc_check.collect_renderers([etc_check.DEFAULT_TARGET]):
        found.extend(etc_check.check_renderer(path))

    assert found == []


def test_collection_covers_both_renderer_types():
    renderers = etc_check.collect_renderers([etc_check.DEFAULT_TARGET])

    assert sum(1 for p in renderers if p.endswith(".mako")) > 0
    assert sum(1 for p in renderers if p.endswith(".py")) > 0


def test_collection_matches_the_registered_py_entries():
    # PyRenderer imports exactly the entries EtcService declares as PY.
    registered = {
        os.path.join(etc_check.DEFAULT_TARGET, (entry.local_path or entry.path) + ".py")
        for group in EtcService.GROUPS.values()
        for entry in group.entries
        if entry.renderer_type == RendererType.PY
    }
    collected = {p for p in etc_check.collect_renderers([etc_check.DEFAULT_TARGET]) if p.endswith(".py")}

    assert collected == registered


def test_script_without_render_is_reported(tmp_path):
    path = tmp_path / "no_render.py"
    path.write_text("x = 1\n")

    assert etc_check.check_script(str(path)) == [
        (os.path.relpath(str(path), etc_check.LOOKUP_BASE), "renderer defines no render()")
    ]


def test_script_with_syntax_error_is_reported(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def render(service, middleware):\n    x = = 1\n")

    problem = etc_check.check_script(str(path))

    assert len(problem) == 1
    assert "SyntaxError" in problem[0][1]


def test_script_with_render_is_accepted(tmp_path):
    path = tmp_path / "fine.py"
    path.write_text("import os\n\n\ndef render(service, middleware):\n    return os.sep\n")

    assert etc_check.check_script(str(path)) == []


@pytest.mark.parametrize(
    "source",
    [
        "def render(service, middleware):\n    pass\n",
        "async def render(service, middleware):\n    pass\n",
        "def _impl():\n    pass\n\n\nrender = _impl\n",
        "from os import sep as render\n",
    ],
)
def test_render_binding_is_recognised_in_every_shape(source):
    assert etc_check.binds_render(ast.parse(source))


def test_render_defined_only_inside_a_function_does_not_count(tmp_path):
    path = tmp_path / "nested.py"
    path.write_text("def outer():\n    def render(service, middleware):\n        pass\n")

    assert etc_check.check_script(str(path)) == [
        (os.path.relpath(str(path), etc_check.LOOKUP_BASE), "renderer defines no render()")
    ]


def test_missing_name_in_template_is_reported():
    assert problems("    from middlewared.api.current import NoSuchModel\n") == [
        "cannot import name 'NoSuchModel' from 'middlewared.api.current'"
    ]


def test_existing_name_in_template_is_accepted():
    assert problems("    from middlewared.api.current import S3AuditMask\n") == []


def test_missing_module_in_template_is_reported():
    assert len(problems("    import no_such_module_at_all\n")) == 1


def test_submodule_import_is_accepted():
    assert problems("    from middlewared.utils import mako\n") == []


@pytest.mark.parametrize(
    "handler",
    [
        "except ImportError",
        "except ModuleNotFoundError",
        "except Exception",
        "except (ValueError, ImportError)",
        "except",
    ],
)
def test_guarded_import_is_skipped(handler):
    body = f"    try:\n        import no_such_module_at_all\n    {handler}:\n        pass\n"
    assert problems(body) == []


def test_mako_try_finally_does_not_guard_imports():
    # Mako wraps render_body in try/finally. That must not hide a broken import.
    assert "finally:" in Template("<%\n    import os\n%>\\\n").code
    assert len(problems("    import no_such_module_at_all\n")) == 1


def test_import_in_handler_is_still_checked():
    body = "    try:\n        pass\n    except ImportError:\n        import no_such_module_at_all\n"
    assert len(problems(body)) == 1


def test_non_renderer_target_is_rejected(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello\n")

    with pytest.raises(SystemExit):
        etc_check.collect_renderers([str(path)])
