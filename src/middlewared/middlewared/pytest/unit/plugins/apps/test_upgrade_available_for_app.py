import pytest

from middlewared.plugins.apps.ix_apps.query import upgrade_available_for_app

VERSION_MAPPING = {
    "community": {
        "actual-budget": {"version": "1.1.13", "app_version": "24.10.1"},
    },
}


def complete_metadata():
    return {
        "custom_app": False,
        "human_version": "24.10.1_1.1.0",
        "metadata": {"name": "actual-budget", "train": "community", "version": "1.1.0"},
        "migrated": False,
        "portals": {},
        "version": "1.1.0",
    }


def test_upgrade_available_for_complete_metadata():
    upgrade_available, latest_version, latest_app_version = upgrade_available_for_app(
        VERSION_MAPPING, complete_metadata()
    )
    assert upgrade_available is True
    assert latest_version == "1.1.13"
    assert latest_app_version == "24.10.1"


@pytest.mark.parametrize(
    "app_metadata",
    [
        # Nothing at all
        {},
        # Missing the catalog metadata dict entirely
        {"custom_app": False, "version": "1.1.0"},
        # Catalog metadata present but missing each key upgrade detection indexes
        {"custom_app": False, "metadata": {"train": "community", "version": "1.1.0"}},
        {"custom_app": False, "metadata": {"name": "actual-budget", "version": "1.1.0"}},
        {"custom_app": False, "metadata": {"name": "actual-budget", "train": "community"}},
        # Catalog metadata is not even a mapping
        {"custom_app": False, "metadata": None},
        # Missing custom_app, which decides which branch we take
        {"metadata": {"name": "actual-budget", "train": "community", "version": "1.1.0"}},
    ],
)
def test_unusable_metadata_does_not_raise(app_metadata):
    assert upgrade_available_for_app(VERSION_MAPPING, app_metadata) == (False, None, None)


@pytest.mark.parametrize("installed_version", ["latest", "", "not a version", "1.1.13/../..", 1.13, None, []])
def test_installed_version_which_cannot_be_parsed_does_not_raise(installed_version):
    # `Version` raises `InvalidVersion` on anything it cannot parse, and an app whose versions
    # cannot be compared simply has no upgrade available
    app_metadata = complete_metadata()
    app_metadata["metadata"]["version"] = installed_version

    assert upgrade_available_for_app(VERSION_MAPPING, app_metadata) == (False, None, None)


@pytest.mark.parametrize("latest_version", ["latest", "", "not a version", None])
def test_catalog_version_which_cannot_be_parsed_does_not_raise(latest_version):
    version_mapping = {"community": {"actual-budget": {"version": latest_version, "app_version": "24.10.1"}}}

    assert upgrade_available_for_app(version_mapping, complete_metadata()) == (False, None, None)


def test_catalog_entry_without_a_version_does_not_raise():
    version_mapping = {"community": {"actual-budget": {"app_version": "24.10.1"}}}

    assert upgrade_available_for_app(version_mapping, complete_metadata()) == (False, None, None)


def test_a_custom_app_never_reports_an_upgrade_from_here():
    # Metadata that would otherwise report an upgrade, so the only thing holding the answer at False
    # is the custom app check. A custom app tracks its image, and whether that image has an update
    # pending is decided by `list_apps`, not here.
    assert upgrade_available_for_app(VERSION_MAPPING, complete_metadata() | {"custom_app": True}) == (
        False, None, None,
    )
