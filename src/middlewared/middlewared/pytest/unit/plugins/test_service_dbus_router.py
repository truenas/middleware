from jeepney import new_error, new_method_return
from jeepney.low_level import HeaderFields
from jeepney.wrappers import DBusErrorResponse
import pytest

from middlewared.plugins.service_.services.dbus_router import CachedSystemDBusRouter


def unit_path(name: str) -> str:
    return "/org/freedesktop/systemd1/unit/" + "".join(c if c.isalnum() else f"_{ord(c):02x}" for c in name)


class FakeSystemd:
    """
    Answer the systemd D-Bus calls that the router makes for unit state, and record them.

    `units` maps the name of each loaded unit to its (ActiveState, MainPID).
    """

    def __init__(self, units: dict[str, tuple[str, int]], error: str = "org.freedesktop.systemd1.NoSuchUnit"):
        self.units = {unit_path(name): state for name, state in units.items()}
        self.error = error
        self.calls: list[tuple[str, tuple]] = []

    async def send(self, msg):
        member = msg.header.fields[HeaderFields.member]
        self.calls.append((member, msg.body))
        if member == "GetUnit":
            if unit_path(msg.body[0]) not in self.units:
                return new_error(msg, self.error, "s", (f"Unit {msg.body[0]} not loaded.",))
            return new_method_return(msg, "o", (unit_path(msg.body[0]),))
        if member == "Get":
            active_state, main_pid = self.units[msg.header.fields[HeaderFields.path]]
            if msg.body[1] == "ActiveState":
                return new_method_return(msg, "v", (("s", active_state),))
            if msg.body[1] == "MainPID":
                return new_method_return(msg, "v", (("u", main_pid),))
        raise AssertionError(f"unexpected call {member} {msg.body}")


def fake_systemd(monkeypatch, units, **kwargs) -> FakeSystemd:
    systemd = FakeSystemd(units, **kwargs)
    monkeypatch.setattr(CachedSystemDBusRouter, "_send", systemd.send)
    return systemd


@pytest.mark.asyncio
async def test_unit_not_loaded_is_inactive_without_loading_it(monkeypatch):
    systemd = fake_systemd(monkeypatch, {})
    router = CachedSystemDBusRouter()
    assert await router.get_service_state("smbd") == (b"inactive", 0)
    assert await router.get_unit_active_state("smbd") == "inactive"
    assert [member for member, body in systemd.calls] == ["GetUnit", "GetUnit"]


@pytest.mark.asyncio
@pytest.mark.parametrize("active_state, main_pid", [("active", 1234), ("failed", 0)])
async def test_loaded_unit_reports_its_state(monkeypatch, active_state, main_pid):
    systemd = fake_systemd(monkeypatch, {"smbd.service": (active_state, main_pid)})
    router = CachedSystemDBusRouter()
    assert await router.get_service_state("smbd") == (active_state.encode(), main_pid)
    assert await router.get_unit_active_state("smbd") == active_state
    assert "LoadUnit" not in [member for member, body in systemd.calls]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, unit",
    [
        ("smbd", "smbd.service"),
        (b"smbd", "smbd.service"),
        ("smbd.service", "smbd.service"),
        ("docker.socket", "docker.socket"),
    ],
)
async def test_unit_is_asked_for_by_its_full_name(monkeypatch, name, unit):
    systemd = fake_systemd(monkeypatch, {})
    await CachedSystemDBusRouter().get_unit_active_state(name)
    assert systemd.calls == [("GetUnit", (unit,))]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get_service_state", "get_unit_active_state"])
async def test_other_errors_are_raised(monkeypatch, method):
    fake_systemd(monkeypatch, {}, error="org.freedesktop.DBus.Error.AccessDenied")
    with pytest.raises(DBusErrorResponse):
        await getattr(CachedSystemDBusRouter(), method)("smbd")
