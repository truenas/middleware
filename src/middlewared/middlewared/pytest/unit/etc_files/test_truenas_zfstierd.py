"""The ZFSTIER entitlement gate on the `truenas_zfstierd` config renderer.

mypy is run with `--exclude middlewared/etc_files`, so nothing else checks this renderer at
all -- this is its only gate.

`etc_files` is not an importable package; `plugins/etc.py` loads it through a path lookup, so
the renderer is loaded here by path too. The output is parsed with `configparser` rather than
matched as text: the INI comes from `truenas_zfstierd_common`, which lowercases keys and
appends defaults this renderer never passes, so string matching would pin formatting that is
not ours.
"""

import importlib.util
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from truenas_pylicensed.features import LicenseFeature

from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware

RENDERER_PATH = Path(__file__).resolve().parents[3] / "etc_files" / "truenas_zfstierd.py"


def _load_renderer():
    spec = importlib.util.spec_from_file_location("etc_files_truenas_zfstierd", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


render = _load_renderer().render


@dataclass
class _TierConfig:
    """Stands in for the `ZfsTierEntry` model `zfs.tier.config` returns."""

    enabled: bool = True
    max_concurrent_jobs: int = 2
    max_used_percentage: int = 80


def _render(column):
    middleware = Middleware()
    install_entitlements_for_column(middleware, LicenseFeature.ZFSTIER, column)
    middleware["zfs.tier.config"] = lambda: _TierConfig()
    parser = ConfigParser()
    parser.read_string(render(None, middleware).decode())
    return parser


def test_enabled_configuration_renders_disabled_without_the_entitlement():
    assert _render("CE").getboolean("GLOBAL", "Enabled") is False


def test_enabled_configuration_renders_enabled_with_the_entitlement():
    assert _render("HW+K").getboolean("GLOBAL", "Enabled") is True
