import pytest
from unittest.mock import AsyncMock, Mock, patch

from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.update_ import UpdateService
from middlewared.plugins.update_.profile_ import post_license_update
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware


def mission_critical(m, entitled):
    return install_entitlements_for_column(m, LicenseFeature.MISSION_CRITICAL, "HW+K" if entitled else "CE+L")


@pytest.mark.asyncio
async def test_profile_choices():
    middleware = Middleware()
    checked = mission_critical(middleware, True)
    middleware.services.update.config_safe = AsyncMock(return_value=Mock(profile=None))

    service = UpdateService(middleware)

    with patch('middlewared.plugins.update_.profile_.current_version_profile', new=AsyncMock(return_value="GENERAL")):
        choices = await service.profile_choices()
        assert list(choices.keys()) == ["GENERAL", "MISSION_CRITICAL"]
        assert choices["GENERAL"].available
        assert choices["GENERAL"].footnote == "(not recommended)"
        assert not choices["MISSION_CRITICAL"].available

    assert checked == [LicenseFeature.MISSION_CRITICAL]


@pytest.mark.asyncio
async def test_profile_choices_current_is_always_available():
    middleware = Middleware()
    checked = mission_critical(middleware, True)
    middleware.services.update.config_safe = AsyncMock(return_value=Mock(profile="MISSION_CRITICAL"))

    service = UpdateService(middleware)

    with patch('middlewared.plugins.update_.profile_.current_version_profile', new=AsyncMock(return_value="GENERAL")):
        choices = await service.profile_choices()
        assert list(choices.keys()) == ["GENERAL", "MISSION_CRITICAL"]
        assert choices["GENERAL"].available
        assert choices["MISSION_CRITICAL"].available

    assert checked == [LicenseFeature.MISSION_CRITICAL]


@pytest.mark.asyncio
async def test_profile_choices_when_not_entitled():
    middleware = Middleware()
    checked = mission_critical(middleware, False)
    middleware.services.update.config_safe = AsyncMock(return_value=Mock(profile=None))

    service = UpdateService(middleware)

    with patch('middlewared.plugins.update_.profile_.current_version_profile', new=AsyncMock(return_value="GENERAL")):
        choices = await service.profile_choices()
        assert list(choices.keys()) == ["DEVELOPER", "EARLY_ADOPTER", "GENERAL"]
        assert all(choice.available for choice in choices.values())
        assert choices["GENERAL"].footnote == "(Default)"

    assert checked == [LicenseFeature.MISSION_CRITICAL]


@pytest.mark.asyncio
async def test_post_license_update_sets_profile_when_entitled():
    middleware = Middleware()
    checked = mission_critical(middleware, True)
    middleware.services.update.set_profile = AsyncMock()

    await post_license_update(middleware, False)

    assert checked == [LicenseFeature.MISSION_CRITICAL]
    middleware.services.update.set_profile.assert_called_once_with("MISSION_CRITICAL")


@pytest.mark.asyncio
async def test_post_license_update_does_nothing_when_not_entitled():
    middleware = Middleware()
    checked = mission_critical(middleware, False)
    middleware.services.update.set_profile = AsyncMock()

    await post_license_update(middleware, False)

    assert checked == [LicenseFeature.MISSION_CRITICAL]
    middleware.services.update.set_profile.assert_not_called()


@pytest.mark.asyncio
async def test_post_license_update_skips_when_already_licensed():
    middleware = Middleware()
    checked = mission_critical(middleware, True)
    middleware.services.update.set_profile = AsyncMock()

    await post_license_update(middleware, True)

    assert checked == []
    middleware.services.update.set_profile.assert_not_called()
