"""Unit tests for the API version import checker."""

from middlewared.test.linter import api_import_check


def test_every_api_version_imports():
    failed = {}
    for version in api_import_check.discover_versions():
        count, error = api_import_check.check_version(version)
        if error is not None:
            failed[version] = error

    assert failed == {}


def test_discovery_finds_the_versions_on_disk():
    versions = api_import_check.discover_versions()

    assert versions
    assert all(v.startswith("v") for v in versions)
    assert "v26_0_0" in versions


def test_discovery_matches_the_directories_the_server_scans():
    # Middleware._create_apis takes every api/v* directory holding __init__.py.
    on_disk = sorted(
        entry.name
        for entry in api_import_check.API_DIR.iterdir()
        if entry.name.startswith("v") and entry.is_dir() and (entry / "__init__.py").exists()
    )

    assert api_import_check.discover_versions() == on_disk


def test_newest_version_reports_its_models():
    newest = api_import_check.discover_versions()[-1]
    count, error = api_import_check.check_version(newest)

    assert error is None
    assert count > 0


def test_failure_returns_a_traceback():
    count, error = api_import_check.check_version("v_no_such_version")

    assert count == 0
    assert error is not None
    assert "ModuleNotFoundError" in error
