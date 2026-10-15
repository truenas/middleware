from jeepney import new_error
from jeepney.low_level import HeaderFields
import pytest

from middlewared.plugins.service.services.dbus_router import CachedSystemDBusRouter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, state",
    [
        ("get_service_state", (b"inactive", 0)),
        ("get_unit_active_state", "inactive"),
    ],
)
async def test_unit_not_loaded_is_inactive_without_loading_it(monkeypatch, method, state):
    calls = []

    async def send(self, msg):
        calls.append(msg.header.fields[HeaderFields.member])
        return new_error(msg, "org.freedesktop.systemd1.NoSuchUnit", "s", ("Unit smbd.service not loaded.",))

    monkeypatch.setattr(CachedSystemDBusRouter, "_send", send)
    assert await getattr(CachedSystemDBusRouter(), method)("smbd") == state
    assert calls == ["GetUnit"]
