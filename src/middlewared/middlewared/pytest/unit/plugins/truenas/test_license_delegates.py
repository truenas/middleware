import ast
import errno
import glob
import importlib
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from truenas_pylicensed import LicenseError
from truenas_pylicensed.features import LicenseFeature

from middlewared.common.license import LicenseDelegate
from middlewared.plugins.truenas.license import ALERT_ONLY, TrueNASLicenseService, setup, snapshot
from middlewared.plugins.vm import VMLicenseDelegate
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware, fake_service_control
from middlewared.service_exception import CallError
from middlewared.utils.entitlements import POLICY
from middlewared.utils.filter_list import filter_list
from middlewared.utils.python import get_middlewared_dir

DELEGATE_KINDS = {"LicenseDelegate", "ConvergeDelegate", "WorkloadDelegate"}


def _base_name(base):
    if isinstance(base, ast.Subscript):
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _modules_declaring_delegates():
    """Found without importing every plugin, at the depth the plugin loader imports."""
    root = get_middlewared_dir()
    paths = glob.glob(os.path.join(root, "plugins", "*.py")) + glob.glob(os.path.join(root, "plugins", "*", "*.py"))
    modules = []
    for path in paths:
        with open(path) as f:
            tree = ast.parse(f.read())

        if any(
            isinstance(node, ast.ClassDef) and any(_base_name(base) in DELEGATE_KINDS for base in node.bases)
            for node in ast.walk(tree)
        ):
            relative = os.path.relpath(path, root).removesuffix(".py").removesuffix("/__init__")
            modules.append("middlewared." + relative.replace(os.sep, "."))

    return sorted(modules)


def test_every_policy_key_has_a_delegate_or_is_alert_only():
    """A POLICY key nobody handles, or a delegate in a module the daemon never imports."""
    # The daemon imports plugins after its entry module, and some plugin packages only import
    # cleanly in that order.
    importlib.import_module("middlewared.main")
    for module in _modules_declaring_delegates():
        importlib.import_module(module)

    delegated = set(LicenseDelegate.by_feature)
    assert sorted(set(POLICY) - delegated - ALERT_ONLY) == []
    assert sorted(delegated & ALERT_ONLY) == []
    for feature, cls in LicenseDelegate.by_feature.items():
        plugin = cls.__module__.removeprefix("middlewared.plugins.")
        assert plugin != cls.__module__ and plugin.count(".") <= 1, (feature, cls.__module__)


@pytest.fixture
def registry():
    with patch.dict(LicenseDelegate.by_feature, clear=True):
        yield


def make_delegate(*features, active_only=False, error=None):
    calls = []

    async def apply(self, changes):
        calls.append(changes)
        if error is not None:
            raise error

    type("FakeDelegate", (LicenseDelegate,), {"features": features, "active_only": active_only, "apply": apply})
    return calls


async def license_service(middleware):
    service = create_service(middleware, TrueNASLicenseService)
    middleware.services.truenas.license = service
    middleware.event_subscribe = Mock()
    middleware["failover.status_refresh"] = AsyncMock()
    middleware.setdefault("failover.in_progress", Mock(return_value=False))
    middleware.setdefault("failover.is_single_master_node", Mock(return_value=False))
    await setup(middleware)
    return service


def live(**entitled):
    return patch(
        "middlewared.plugins.truenas.license.snapshot",
        Mock(return_value={key: entitled.get(key, False) for key in POLICY}),
    )


@pytest.mark.asyncio
async def test_two_feature_delegate_is_applied_once(registry):
    """One restart per change for a delegate that owns several keys, not one per key."""
    calls = make_delegate(LicenseFeature.S3_AUDIT, LicenseFeature.S3_VERSIONING)
    service = await license_service(Middleware())

    with live(S3_AUDIT=True, S3_VERSIONING=True):
        await service.apply(FakeJob(), {"S3_AUDIT": True, "S3_VERSIONING": True})

    assert calls == [{"S3_AUDIT": True, "S3_VERSIONING": True}]


@pytest.mark.asyncio
async def test_failing_delegate_does_not_stop_the_rest(registry):
    make_delegate(LicenseFeature.SMB_BLOCK_CLONING, error=CallError("cifs reload failed"))
    calls = make_delegate(LicenseFeature.ZFSTIER)
    service = await license_service(Middleware())

    with live(), pytest.raises(CallError, match="SMB_BLOCK_CLONING: cifs reload failed"):
        await service.apply(FakeJob(), {"SMB_BLOCK_CLONING": False, "ZFSTIER": False})

    assert calls == [{"ZFSTIER": False}]


@pytest.mark.asyncio
async def test_active_only_delegate_is_skipped_on_backup(registry):
    active_calls = make_delegate(LicenseFeature.APPS, active_only=True)
    both_calls = make_delegate(LicenseFeature.SUPPORT)
    middleware = Middleware()
    middleware["failover.in_progress"] = Mock(return_value=False)
    middleware["failover.is_single_master_node"] = Mock(return_value=False)
    service = await license_service(middleware)

    with live():
        await service.apply(FakeJob(), {"APPS": False, "SUPPORT": False})

    assert active_calls == []
    assert both_calls == [{"SUPPORT": False}]


@pytest.mark.asyncio
async def test_key_disagreeing_with_installed_license_is_skipped(registry):
    """A stale replay or a mistyped manual call must not revoke a feature the license grants."""
    apps_calls = make_delegate(LicenseFeature.APPS)
    make_delegate(LicenseFeature.ZFSTIER)
    service = await license_service(Middleware())

    with live(APPS=True, ZFSTIER=True):
        result = await service.apply(FakeJob(), {"APPS": False, "ZFSTIER": True})

    assert result == {"applied": ["ZFSTIER"], "skipped": ["APPS"]}
    assert apps_calls == []


@pytest.mark.asyncio
async def test_failed_revoke_check_leaves_the_usage_alert_alone(registry):
    middleware = Middleware()
    middleware.services.truenas.entitlements.usage = AsyncMock(
        return_value={str(LicenseFeature.DEDUP): {"entitled": False, "in_use": True, "message": "x"}}
    )
    service = await license_service(middleware)

    with patch(
        "middlewared.plugins.truenas.license.snapshot",
        Mock(side_effect=CallError("license daemon unavailable", errno.EAGAIN)),
    ):
        await service.refresh_usage_alert()

    middleware.services.alert.oneshot_create.assert_not_called()
    middleware.services.alert.oneshot_delete.assert_not_called()


@pytest.mark.asyncio
async def test_ha_in_use_alone_clears_the_usage_alert(registry):
    middleware = Middleware()
    middleware.services.truenas.entitlements.usage = AsyncMock(
        return_value={str(LicenseFeature.HA): {"entitled": False, "in_use": True, "message": "x"}}
    )
    service = await license_service(middleware)

    with live():
        await service.refresh_usage_alert()

    middleware.services.alert.oneshot_delete.assert_called_once_with("UnlicensedFeaturesInUse", None)
    middleware.services.alert.oneshot_create.assert_not_called()


def delegate(started, result=True, active=True):
    middleware = Middleware()
    middleware.services.service.started = Mock(return_value=started)
    middleware["failover.in_progress"] = Mock(return_value=False)
    middleware["failover.is_single_master_node"] = Mock(return_value=active)
    return LicenseDelegate(middleware), fake_service_control(middleware, result)


@pytest.mark.asyncio
async def test_restart_of_stopped_service_is_skipped():
    """A RESTART would start a service the user stopped."""
    d, calls = delegate(started=False)
    await d.control("cifs", "RESTART")
    assert calls == []


@pytest.mark.asyncio
async def test_reload_of_stopped_service_renders_without_failing():
    d, calls = delegate(started=False, result=False)
    await d.control("truenas_zfstierd", "RELOAD")
    assert calls == [("RELOAD", "truenas_zfstierd", {"silent": False, "ha_propagate": False, "timeout": 120})]


@pytest.mark.asyncio
async def test_false_from_running_service_raises():
    d, _ = delegate(started=True, result=False)
    with pytest.raises(CallError, match="cifs: RELOAD"):
        await d.control("cifs", "RELOAD")


@pytest.mark.asyncio
async def test_start_on_standby_needs_standby_ok():
    d, calls = delegate(started=False, active=False)
    await d.control("ctdb", "START")
    assert calls == []

    await d.control("ctdb", "START", standby_ok=True)
    assert [call[0] for call in calls] == ["START"]


@pytest.mark.asyncio
async def test_running_override_restarts_a_unit_still_activating():
    """S3 reads as stopped for minutes while registering and must still be restarted."""
    d, calls = delegate(started=False)
    await d.control("s3", "RESTART", running=True)
    assert [call[0] for call in calls] == ["RESTART"]


@pytest.mark.parametrize(
    "code", [LicenseError.DAEMON_UNAVAILABLE, LicenseError.DAEMON_ERROR, LicenseError.INTERNAL_ERROR]
)
def test_snapshot_refuses_daemon_errors(code):
    """A daemon blip read as unlicensed would revoke every feature."""
    with pytest.raises(CallError) as e:
        snapshot(Mock(code=code))
    assert e.value.errno == errno.EAGAIN


def vm_row(id_, autostart, state):
    return {"id": id_, "name": f"vm{id_}", "autostart": autostart, "status": {"state": state}}


def workload(rows, start_errors=(), running_after_error=()):
    """A delegate over a fake `vm` namespace holding `rows`, and the list of ids `vm.start` was called with."""
    started = []

    def query(filters):
        return [
            SimpleNamespace(id=row["id"], name=row["name"], status=SimpleNamespace(state=row["status"]["state"]))
            for row in filter_list(rows, filters)
        ]

    def start(id_, options):
        started.append(id_)
        if id_ in running_after_error:
            filter_list(rows, [["id", "=", id_]], {"get": True})["status"]["state"] = "RUNNING"
        if id_ in start_errors:
            raise CallError("start failed")

    middleware = Middleware()
    middleware["failover.in_progress"] = Mock(return_value=False)
    middleware["failover.is_single_master_node"] = Mock(return_value=True)
    middleware.services.vm.query = query
    middleware.services.vm.get_instance = lambda id_: query([["id", "=", id_]])[0]
    middleware.services.vm.start = start
    return VMLicenseDelegate(middleware), started


@pytest.mark.asyncio
async def test_workload_grant_starts_only_stopped_autostart_instances():
    """A grant starting VMs the user did not mark autostart, or restarting ones already up."""
    d, started = workload([vm_row(1, True, "STOPPED"), vm_row(2, True, "RUNNING"), vm_row(3, False, "STOPPED")])

    await d._start_autostart()

    assert started == [1]


@pytest.mark.asyncio
async def test_workload_grant_ignores_a_start_error_once_the_instance_is_up():
    """A start that raises but leaves the VM running is not a failure."""
    d, started = workload(
        [vm_row(1, True, "STOPPED"), vm_row(2, True, "STOPPED")], start_errors={1, 2}, running_after_error={1}
    )

    with pytest.raises(CallError) as e:
        await d._start_autostart()

    assert started == [1, 2]
    assert "vm2" in e.value.errmsg and "vm1" not in e.value.errmsg
