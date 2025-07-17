import pytest

from auto_config import ha
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, mock


@pytest.fixture(autouse=True)
def null_profile():
    profile = call("update.config_internal")["profile"]
    call("datastore.update", "system.update", 1, {"upd_profile": None})
    yield
    call("datastore.update", "system.update", 1, {"upd_profile": profile})


@pytest.fixture(scope="module")
def offline():
    with mock("network.general.can_perform_activity", return_value=False):
        yield


def test_update():
    # `update.config` should set the profile
    profile_setting = "DEVELOPER"  # default profile on nightly builds (including HA)
    original_config = call("update.config")
    assert original_config["profile"] == profile_setting

    if ha:
        with mock("update.profile_choices", return_value={profile_setting: {"available": True}}):
            # "DEVELOPER" profile not normally available on HA
            updated_config = call("update.update", {})
    else:
        updated_config = call("update.update", {})
    assert updated_config == original_config


def test_update_invalid_profile():
    with pytest.raises(ValidationErrors, match="Invalid profile."):
        call("update.update", {"profile": "INVALID"})


def test_config_internal(offline):
    # `update.config_internal` should allow null profile
    config = call("update.config_internal")
    assert config["profile"] is None


def test_set_profile(offline):
    profile_setting = "GENERAL"
    call("update.set_profile", profile_setting)
    assert call("update.config")["profile"] == profile_setting
