import pytest

from middlewared.api.base import BaseModel, LibvirtUUID
from middlewared.api.base.handler.accept import accept_params
from middlewared.api.v27_0_0.container import ContainerCreate, ContainerEntry
from middlewared.api.v27_0_0.vm import VMCreate, VMEntry
from middlewared.service_exception import ValidationErrors
from middlewared.utils.libvirt.utils import same_uuid


class LibvirtUUIDModel(BaseModel):
    uuid: LibvirtUUID


@pytest.mark.parametrize(
    "value,expected",
    [
        ("550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440000"),
        ("550E8400-E29B-41D4-A716-446655440000", "550e8400-e29b-41d4-a716-446655440000"),
        ("550e8400e29b41d4a716446655440000", "550e8400-e29b-41d4-a716-446655440000"),
        ("550e8400e29b-41d4a716446655440000", "550e8400-e29b-41d4-a716-446655440000"),
    ],
)
def test_libvirt_uuid_accepts_and_normalizes(value, expected):
    assert accept_params(LibvirtUUIDModel, [value]) == [expected]


@pytest.mark.parametrize(
    "value",
    [
        "{550e8400-e29b-41d4-a716-446655440000}",
        "urn:uuid:550e8400-e29b-41d4-a716-446655440000",
        "550e8400 e29b 41d4 a716 446655440000",
        "",
        "not-a-uuid-at-all",
        "550e8400e29b41d4a71644665544000",
        "550e8400e29b41d4a7164466554400000",
        " 550e8400-e29b-41d4-a716-446655440000",
        "550e8400-e29b-41d4-a716-446655440000 ",
    ],
)
def test_libvirt_uuid_rejects_invalid(value):
    with pytest.raises(ValidationErrors) as ve:
        accept_params(LibvirtUUIDModel, [value])

    assert "UUID must be 32 hexadecimal digits" in ve.value.errors[0].errmsg


@pytest.mark.parametrize(
    "value,expected",
    [
        ("42250ee6-f5eb-8576-46f1-f1f5c19cbf2a", "42250ee6-f5eb-8576-46f1-f1f5c19cbf2a"),
        ("494BE480-0C2F-11DA-ABB6-72CC4387A395", "494be480-0c2f-11da-abb6-72cc4387a395"),
        ("3e1c05e7-aca6-5a54-b713-8252e366b786", "3e1c05e7-aca6-5a54-b713-8252e366b786"),
        ("494be4800c2f11daabb672cc4387a395", "494be480-0c2f-11da-abb6-72cc4387a395"),
    ],
)
def test_libvirt_uuid_accepts_non_v4(value, expected):
    assert accept_params(LibvirtUUIDModel, [value]) == [expected]


@pytest.mark.parametrize("entry,create", [(VMEntry, VMCreate), (ContainerEntry, ContainerCreate)])
def test_entry_is_plain_str_and_create_validates(entry, create):
    entry_field = entry.model_fields["uuid"]
    assert entry_field.annotation is str
    assert entry_field.metadata == []

    assert create.model_fields["uuid"].annotation == LibvirtUUID | None


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("550E8400-E29B-41D4-A716-446655440000", "550e8400e29b41d4a716446655440000", True),
        ("550e8400-e29b-41d4-a716-446655440000", "42250ee6-f5eb-8576-46f1-f1f5c19cbf2a", False),
        ("", "", True),
        ("garbage", "other", False),
        ("550e8400-e29b-41d4-a716-446655440000", "garbage", False),
    ],
)
def test_same_uuid(a, b, expected):
    assert same_uuid(a, b) is expected
