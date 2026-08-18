import pytest
from truenas_pylicensed import LicenseType

from middlewared.pytest.unit.entitlements import make_license
from middlewared.utils.entitlements import get_facts
from middlewared.utils.hardware import HardwareClass


@pytest.mark.parametrize("hardware_class", list(HardwareClass))
@pytest.mark.parametrize("licensed", [True, False])
def test_facts_are_read_from_the_system(monkeypatch, hardware_class, licensed):
    license = make_license(type_=LicenseType.ENTERPRISE_HA) if licensed else None
    monkeypatch.setattr("middlewared.utils.entitlements.system.get_hardware_class", lambda: hardware_class)
    monkeypatch.setattr("middlewared.utils.entitlements.system.get_license", lambda: license)

    facts = get_facts()

    assert facts.hardware_class is hardware_class
    assert facts.license is license


def test_license_is_re_read_on_every_call(monkeypatch):
    """A license can be uploaded or removed under a running middlewared, so nothing here may be cached."""
    licenses = [None, make_license(type_=LicenseType.ENTERPRISE_HA)]
    calls = []

    def get_license():
        calls.append(None)
        return licenses[len(calls) - 1]

    monkeypatch.setattr("middlewared.utils.entitlements.system.get_hardware_class", lambda: HardwareClass.TRUENAS_HW)
    monkeypatch.setattr("middlewared.utils.entitlements.system.get_license", get_license)

    assert get_facts().license is None
    assert get_facts().license is licenses[1]
    assert len(calls) == 2
