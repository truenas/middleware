import contextlib
import io
import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from middlewared.plugins.apps.metadata import app_metadata_generate
from middlewared.utils.yaml import safe_yaml_load


def app_metadata(version="1.1.0"):
    return {
        "custom_app": False,
        "human_version": f"24.10.1_{version}",
        "metadata": {"name": "actual-budget", "train": "community", "version": version},
        "migrated": False,
        "notes": None,
        "portals": {},
        "version": version,
    }


class FakeDirEntry:
    def __init__(self, name):
        self.name = name

    def is_dir(self):
        return True


@contextlib.contextmanager
def generate(app_names, metadata_map, config_side_effect):
    """Run `app_metadata_generate` against fake apps, yielding what it wrote to disk."""
    written = {}

    @contextlib.contextmanager
    def fake_atomic_write(path, *args, **kwargs):
        f = io.StringIO()
        yield f
        written[path] = safe_yaml_load(f.getvalue()) or {}

    scandir = MagicMock()
    scandir.return_value.__enter__.return_value = [FakeDirEntry(name) for name in app_names]

    with (
        patch("middlewared.plugins.apps.metadata.os.scandir", scandir),
        patch("middlewared.plugins.apps.metadata.atomic_write", fake_atomic_write),
        patch("middlewared.plugins.apps.metadata.get_app_metadata", side_effect=lambda name: metadata_map[name]),
        patch("middlewared.plugins.apps.metadata.get_current_app_config", side_effect=config_side_effect),
        patch("middlewared.plugins.apps.metadata.get_collective_metadata_path", return_value="metadata.yaml"),
        patch("middlewared.plugins.apps.metadata.get_collective_config_path", return_value="user_config.yaml"),
    ):
        app_metadata_generate(MagicMock())

    yield written["metadata.yaml"], written["user_config.yaml"]


def test_healthy_apps_are_collected():
    metadata_map = {"app-a": app_metadata(), "app-b": app_metadata("2.0.0")}
    with generate(["app-a", "app-b"], metadata_map, lambda name, version: {"name": name}) as (metadata, config):
        assert sorted(metadata) == ["app-a", "app-b"]
        assert sorted(config) == ["app-a", "app-b"]


@pytest.mark.parametrize(
    "broken_metadata,failing_config",
    [
        # `version` is absent, so building the app's config raises KeyError
        ({"custom_app": False, "metadata": {"name": "b", "train": "community"}}, False),
        # `version` is present but its config cannot be read (mode 3)
        (app_metadata(), True),
    ],
)
def test_one_broken_app_does_not_stop_the_others(broken_metadata, failing_config):
    metadata_map = {"app-a": app_metadata(), "app-broken": broken_metadata, "app-b": app_metadata("2.0.0")}

    def get_config(name, version):
        if name == "app-broken" and failing_config:
            raise FileNotFoundError(2, "No such file or directory")
        return {"name": name}

    with generate(["app-a", "app-broken", "app-b"], metadata_map, get_config) as (metadata, config):
        # The healthy apps still land on disk, and so does the broken one's metadata - only the
        # config it has none of is left out.
        assert sorted(metadata) == ["app-a", "app-b", "app-broken"]
        assert sorted(config) == ["app-a", "app-b"]


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError(2, "No such file or directory"),
        IsADirectoryError(21, "Is a directory"),
        yaml.YAMLError("could not parse"),
        ValueError("not a mapping"),
        KeyError("version"),
    ],
)
def test_app_whose_config_cannot_be_read_keeps_its_metadata(error):
    """
    Whatever the app's config died of, its metadata stays in the collective file. Being absent from
    that file is how an app becomes invisible to `app.query`, and an app nobody can see is an app
    nobody can delete.
    """
    metadata_map = {"app-broken": app_metadata()}

    def get_config(name, version):
        raise error

    with generate(["app-broken"], metadata_map, get_config) as (metadata, config):
        assert sorted(metadata) == ["app-broken"]
        assert config == {}


def test_broken_app_is_logged(caplog):
    metadata_map = {"app-broken": app_metadata()}

    def get_config(name, version):
        raise FileNotFoundError(2, "No such file or directory")

    with caplog.at_level(logging.WARNING, logger="app_lifecycle"):
        with generate(["app-broken"], metadata_map, get_config) as (metadata, config):
            assert sorted(metadata) == ["app-broken"]
            assert config == {}

    assert "app-broken: app config could not be read" in caplog.text


def test_unreadable_metadata_is_skipped():
    # `get_app_metadata` collapses an unreadable/unparseable file to an empty dict
    metadata_map = {"app-a": app_metadata(), "app-broken": {}}
    with generate(["app-a", "app-broken"], metadata_map, lambda name, version: {"name": name}) as (metadata, config):
        assert sorted(metadata) == ["app-a"]
        assert sorted(config) == ["app-a"]
