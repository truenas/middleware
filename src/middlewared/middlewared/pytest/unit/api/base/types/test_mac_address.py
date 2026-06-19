import pydantic
import pytest

from middlewared.api.base import BaseModel, MACAddress
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.v27_0_0.container_device import ContainerNICDevice
from middlewared.api.v27_0_0.vm_device import VMNICDevice
from middlewared.service_exception import ValidationErrors


class MACAddressModel(BaseModel):
    mac: MACAddress


@pytest.mark.parametrize(
    "value",
    [
        "00:a0:99:7e:bb:8a",  # canonical lowercase
        "00:A0:99:7E:BB:8A",  # uppercase colon (libvirt accepts and lowercases)
    ],
)
def test_mac_address_accepts_colon(value):
    assert accept_params(MACAddressModel, [value]) == [value]


@pytest.mark.parametrize(
    "value",
    [
        "10-66-6a-1f-f1-b1",  # dash separators
        "10-66-6A-1F-F1-B1",  # dash separators, uppercase
        "00a0997ebb8a",  # no separators
        "00:a0-99:7e-bb:8a",  # mixed separators
        "00:a0:99:7e:bb",  # too short
        "gg:gg:gg:gg:gg:gg",  # colon-separated but non-hex
    ],
)
def test_mac_address_rejects_non_colon(value):
    with pytest.raises(ValidationErrors) as ve:
        accept_params(MACAddressModel, [value])

    assert "colon-separated" in ve.value.errors[0].errmsg


@pytest.mark.parametrize("model", [VMNICDevice, ContainerNICDevice])
def test_nic_device_mac_accepts_colon(model):
    assert model(dtype="NIC", mac="00:a0:99:7e:bb:8a").mac == "00:a0:99:7e:bb:8a"


@pytest.mark.parametrize("model", [VMNICDevice, ContainerNICDevice])
def test_nic_device_mac_allows_null(model):
    assert model(dtype="NIC", mac=None).mac is None


@pytest.mark.parametrize("model", [VMNICDevice, ContainerNICDevice])
def test_nic_device_mac_rejects_dash(model):
    with pytest.raises(pydantic.ValidationError):
        model(dtype="NIC", mac="10-66-6a-1f-f1-b1")
