import os

import pytest
import yaml

from middlewared.plugins.apps.ix_apps.metadata import (
    APP_CATALOG_METADATA_REQUIRED_KEYS,
    APP_METADATA_REQUIRED_KEYS,
    app_metadata_error,
    get_app_metadata_checked,
    resolve_app_metadata,
)


def complete_metadata():
    return {
        "custom_app": False,
        "human_version": "24.10.1_1.1.13",
        "metadata": {"name": "actual-budget", "train": "community", "version": "1.1.13"},
        "migrated": False,
        "notes": None,
        "portals": {},
        "version": "1.1.13",
    }


def test_complete_metadata_is_usable():
    assert app_metadata_error(complete_metadata()) is None


def test_empty_metadata_is_missing():
    assert app_metadata_error({}) == "METADATA_MISSING"


@pytest.mark.parametrize("key", sorted(APP_METADATA_REQUIRED_KEYS))
def test_absent_required_key_is_incomplete(key):
    app_metadata = complete_metadata()
    app_metadata.pop(key)

    assert app_metadata_error(app_metadata) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("key", sorted(APP_CATALOG_METADATA_REQUIRED_KEYS))
def test_absent_catalog_metadata_key_is_incomplete(key):
    app_metadata = complete_metadata()
    app_metadata["metadata"].pop(key)

    assert app_metadata_error(app_metadata) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("catalog_metadata", [None, "actual-budget", [], 1])
def test_catalog_metadata_which_is_not_a_mapping_is_incomplete(catalog_metadata):
    assert app_metadata_error(complete_metadata() | {"metadata": catalog_metadata}) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("app_metadata", ["actual-budget", 1, 1.13, True, ["actual-budget"]])
def test_metadata_which_is_not_a_mapping_is_incomplete(app_metadata):
    # An app's entry in the collective metadata file is whatever yaml parsed it as, and testing a
    # non-mapping for the keys we need raises rather than answering
    assert app_metadata_error(app_metadata) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("key", sorted(APP_METADATA_REQUIRED_KEYS - {"metadata", "custom_app"}))
@pytest.mark.parametrize("value", [None, "", 1.13, True, [], {}])
def test_version_which_is_not_a_non_empty_string_is_incomplete(key, value):
    # Both name a directory or are reported to API consumers as a non-empty string, and yaml parses
    # an unquoted 1.13 as a float
    assert app_metadata_error(complete_metadata() | {key: value}) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("key", ["custom_app", "migrated"])
@pytest.mark.parametrize("value", [None, "", "false", 0, 1, []])
def test_flag_which_is_not_a_bool_is_incomplete(key, value):
    assert app_metadata_error(complete_metadata() | {key: value}) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("portals", ["http://0.0.0.0:8080", 1, ["http://0.0.0.0:8080"]])
def test_portals_which_are_not_a_mapping_is_incomplete(portals):
    assert app_metadata_error(complete_metadata() | {"portals": portals}) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("notes", [1, ["a", "b"], {"a": "b"}])
def test_notes_which_are_not_a_string_is_incomplete(notes):
    assert app_metadata_error(complete_metadata() | {"notes": notes}) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("key", sorted(APP_CATALOG_METADATA_REQUIRED_KEYS))
@pytest.mark.parametrize("value", [None, "", 1.13, True, [], {}])
def test_catalog_metadata_value_which_is_not_a_non_empty_string_is_incomplete(key, value):
    app_metadata = complete_metadata()
    app_metadata["metadata"][key] = value

    assert app_metadata_error(app_metadata) == "METADATA_INCOMPLETE"


@pytest.mark.parametrize("notes", [None, "Some notes"])
def test_notes_a_string_or_null_is_usable(notes):
    assert app_metadata_error(complete_metadata() | {"notes": notes}) is None


@pytest.mark.parametrize("key", ["notes", "migrated", "portals", "action_required"])
def test_defaulted_keys_are_not_required(key):
    # Metadata written by older releases can be missing these, and reporting a working app as broken
    # would take away every operation but deletion
    app_metadata = complete_metadata()
    app_metadata.pop(key, None)

    assert app_metadata_error(app_metadata) is None


@pytest.fixture
def app_configs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "middlewared.plugins.apps.ix_apps.metadata.get_installed_app_metadata_path",
        lambda app_name: os.path.join(tmp_path, app_name, "metadata.yaml"),
    )
    return tmp_path


def write_metadata(app_configs, app_name, contents):
    app_dir = app_configs / app_name
    app_dir.mkdir()
    (app_dir / "metadata.yaml").write_text(contents)


def test_readable_metadata_is_returned(app_configs):
    write_metadata(app_configs, "app-a", 'version: "1.1.13"\n')

    assert get_app_metadata_checked("app-a") == ({"version": "1.1.13"}, "METADATA_INCOMPLETE")


def test_absent_metadata_file_is_missing(app_configs):
    (app_configs / "app-a").mkdir()

    assert get_app_metadata_checked("app-a") == ({}, "METADATA_MISSING")


def test_unparseable_metadata_is_unreadable(app_configs):
    write_metadata(app_configs, "app-a", "{")

    assert get_app_metadata_checked("app-a") == ({}, "METADATA_UNREADABLE")


def test_metadata_which_is_not_a_mapping_is_unreadable(app_configs):
    write_metadata(app_configs, "app-a", "- a\n- b\n")

    assert get_app_metadata_checked("app-a") == ({}, "METADATA_UNREADABLE")


def test_metadata_we_cannot_open_is_unreadable(app_configs):
    # A directory where the file should be stands in for any of EACCES/EIO/EISDIR
    (app_configs / "app-a" / "metadata.yaml").mkdir(parents=True)

    assert get_app_metadata_checked("app-a") == ({}, "METADATA_UNREADABLE")


def test_metadata_in_collective_costs_no_io(app_configs):
    # Nothing is written to `app_configs`, so a filesystem read would fail to find anything
    collective = {"app-a": complete_metadata()}

    assert resolve_app_metadata("app-a", collective, True, set()) == (complete_metadata(), None, True)


def test_incomplete_metadata_in_collective_is_reported(app_configs):
    collective = {"app-a": {"version": "1.1.13"}}

    app_metadata, error_reason, present = resolve_app_metadata("app-a", collective, True, set())

    assert (error_reason, present) == ("METADATA_INCOMPLETE", True)


def test_intact_metadata_outside_collective_is_ignored(app_configs):
    # An install or delete in flight, or a collective metadata file which is itself unreadable
    write_metadata(app_configs, "app-a", yaml.safe_dump(complete_metadata()))

    assert resolve_app_metadata("app-a", {}, False, set()) == (complete_metadata(), None, False)


def test_unreadable_metadata_outside_collective_is_reported(app_configs):
    write_metadata(app_configs, "app-a", "{")

    assert resolve_app_metadata("app-a", {}, False, set()) == ({}, "METADATA_UNREADABLE", True)


def test_absent_metadata_is_reported_when_not_installing(app_configs):
    (app_configs / "app-a").mkdir()

    assert resolve_app_metadata("app-a", {}, False, set()) == ({}, "METADATA_MISSING", True)


def test_absent_metadata_is_ignored_while_installing(app_configs):
    # The app directory is created moments before its metadata is written to it
    (app_configs / "app-a").mkdir()

    assert resolve_app_metadata("app-a", {}, False, {"app-a"}) == ({}, None, False)


def test_absent_metadata_is_reported_while_installing_if_resources_exist(app_configs):
    # Containers only exist once the metadata has been written, so there is no install window here
    (app_configs / "app-a").mkdir()

    assert resolve_app_metadata("app-a", {}, True, {"app-a"}) == ({}, "METADATA_MISSING", True)
