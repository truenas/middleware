import ast
import glob
import importlib
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.common.license import LicenseDelegate
from middlewared.plugins.truenas.license import ALERT_ONLY
from middlewared.plugins.vm import VMLicenseDelegate
from middlewared.pytest.unit.middleware import Middleware, fake_service_control
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


@pytest.mark.asyncio
async def test_restart_of_stopped_service_is_skipped():
    """A RESTART would start a service the user stopped."""
    middleware = Middleware()
    middleware.services.service.started = Mock(return_value=False)
    calls = fake_service_control(middleware, True)

    await LicenseDelegate(middleware).control("cifs", "RESTART")

    assert calls == []


def vm_row(id_, autostart, state):
    return {"id": id_, "name": f"vm{id_}", "autostart": autostart, "status": {"state": state}}


@pytest.mark.asyncio
async def test_workload_grant_starts_only_stopped_autostart_instances():
    """A grant starting VMs the user did not mark autostart, or restarting ones already up."""
    rows = [vm_row(1, True, "STOPPED"), vm_row(2, True, "RUNNING"), vm_row(3, False, "STOPPED")]
    started = []
    middleware = Middleware()
    middleware["failover.in_progress"] = Mock(return_value=False)
    middleware["failover.is_single_master_node"] = Mock(return_value=True)
    middleware.services.vm.query = lambda filters: [
        SimpleNamespace(id=row["id"], name=row["name"]) for row in filter_list(rows, filters)
    ]
    middleware.services.vm.start = lambda id_, options: started.append(id_)

    await VMLicenseDelegate(middleware)._start_autostart()

    assert started == [1]
