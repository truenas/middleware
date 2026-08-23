import logging
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.apps.ix_apps.path import get_app_volume_path
from middlewared.plugins.apps.schema_validation import validate_acl_entries
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext, ValidationErrors

APP_VOLUME_PATH = get_app_volume_path("plex")
SCHEMA_NAME = "app_update.values.storage.data.acl_entries"
ENTRIES = [{"id_type": "USER", "id": 568, "access": "FULL_CONTROL"}]


@pytest.mark.parametrize(
    "value, expected_error, probe_called",
    [
        (
            {"path": "", "entries": ENTRIES, "options": {"force": False}},
            None,
            False,
        ),
        (
            {"path": "/mnt/tank/data", "entries": ENTRIES, "options": {"force": True}},
            None,
            False,
        ),
        # A host path belongs to the user, so the existing data guard still has to fire for it
        (
            {"path": "/mnt/tank/data", "entries": ENTRIES, "options": {"force": False}},
            "path contains existing data",
            True,
        ),
        (
            {"path": APP_VOLUME_PATH, "entries": ENTRIES, "options": {"force": False}},
            None,
            False,
        ),
        # Everything below sits under the app mounts directory, which middleware owns in its entirety, so the
        # pre-flight probe is skipped for all of it - including another app's volume, an app whose name merely
        # shares a prefix with ours, and a host path which was typed under a volume directory. None of these
        # gain the ability to write an ACL: `force` is only ever stamped onto the requesting app's own volume,
        # so add_to_acl still refuses them at apply time, just with a later and less well scoped error
        (
            {"path": f"{APP_VOLUME_PATH}/nested/dir", "entries": ENTRIES, "options": {"force": False}},
            None,
            False,
        ),
        (
            {"path": f"{get_app_volume_path('sonarr')}/data", "entries": ENTRIES, "options": {"force": False}},
            None,
            False,
        ),
        (
            {"path": get_app_volume_path("plex-extra"), "entries": ENTRIES, "options": {"force": False}},
            None,
            False,
        ),
        # Traversal back out of the app mounts directory lands on the user's own data again
        (
            {
                "path": f"{APP_VOLUME_PATH}/../../../../mnt/tank/data",
                "entries": ENTRIES,
                "options": {"force": False},
            },
            "path contains existing data",
            True,
        ),
        # An absent options key reads as force not being specified
        (
            {"path": "/mnt/tank/data", "entries": ENTRIES},
            "path contains existing data",
            True,
        ),
        # An ix volume with its ACL turned off still carries a path and whatever force value was
        # stored with it, so it has to be exempt here as well
        (
            {"path": APP_VOLUME_PATH, "entries": [], "options": {"force": False}},
            None,
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_validate_acl_entries(value, expected_error, probe_called):
    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    verrors = ValidationErrors()
    probe = Mock(return_value=True)

    with patch("middlewared.plugins.apps.schema_validation._acl_path_has_data", probe):
        await validate_acl_entries(ctx, verrors, value, SCHEMA_NAME, None)

    assert probe.called is probe_called
    if expected_error is None:
        assert verrors.errors == []
    else:
        assert len(verrors.errors) == 1
        assert verrors.errors[0].attribute == SCHEMA_NAME
        assert expected_error in verrors.errors[0].errmsg


@pytest.mark.asyncio
async def test_validate_acl_entries_missing_path():
    ctx = ServiceContext(Middleware(), logging.getLogger("test"))
    verrors = ValidationErrors()
    value = {"path": "/mnt/tank/data", "entries": ENTRIES, "options": {"force": False}}

    with patch("middlewared.plugins.apps.schema_validation._acl_path_has_data", Mock(side_effect=FileNotFoundError())):
        await validate_acl_entries(ctx, verrors, value, SCHEMA_NAME, None)

    assert len(verrors.errors) == 1
    assert "path does not exist" in verrors.errors[0].errmsg
