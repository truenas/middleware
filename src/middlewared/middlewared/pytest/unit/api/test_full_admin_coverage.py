"""Guards the `FullAdmin` field marker against the two ways it can silently stop protecting anything.

A field is marked in an API model, but nothing in that model makes the restriction happen: enforcement lives in
`CRUDService.create` / `CRUDService.update` / `ConfigService.update`, and a method that does not route through
those wrappers has to call `check_full_admin_model` itself. Marking a field on such a method's model looks right
and does nothing, which is exactly the class of hole NAS-142146 was. `test_every_marked_field_is_enforced` fails
in that case.

`test_marked_fields_match_the_inventory` then pins the protected set, so that adding to it or (more importantly)
quietly dropping a marker is a visible diff rather than a silent loss of a privilege boundary.
"""

import ast
import importlib
import os
import pathlib

import pytest

import middlewared
import middlewared.api
from middlewared.api.base import BaseModel
from middlewared.api.base.handler.full_admin import full_admin_fields

ENFORCEMENT_HELPER = "check_full_admin_model"
"""What a method that bypasses the CRUD and config wrappers must call to enforce its own marked fields."""

WRAPPED_METHODS = frozenset({"do_create", "do_update"})
"""Method names whose marked fields `CRUDService` and `ConfigService` check before dispatching to them."""

INVENTORY = {
    # Arbitrary rsync flags. `-e` / `--rsh` names the program rsync spawns, as the task's `user`.
    ("RsyncTaskCreateArgs", "rsync_task_create.extra"),
    ("RsyncTaskUpdateArgs", "rsync_task_update.extra"),
    # Interpolated verbatim into sshd_config. `AuthorizedKeysCommand` runs a program as root.
    ("SSHUpdateArgs", "data.options"),
    # Interpolated verbatim into proftpd.conf. `RootLogin` / `DefaultRoot` yield root file access over FTP.
    ("FTPUpdateArgs", "data.options"),
    # Interpolated verbatim into snmpd.conf. net-snmp's `extend` and `exec` run commands as the daemon.
    ("SNMPUpdateArgs", "snmp_update.options"),
    # `shutdowncmd` is run by upsmon as root; the rest are raw passthrough into the NUT config files.
    ("UPSUpdateArgs", "data.extrausers"),
    ("UPSUpdateArgs", "data.options"),
    ("UPSUpdateArgs", "data.optionsupsd"),
    ("UPSUpdateArgs", "data.shutdowncmd"),
    # Kernel command line. `init=/bin/sh` is root at next boot.
    ("SystemAdvancedUpdateArgs", "data.kernel_extra_options"),
    # Raw QEMU args, bypassing the device model entirely.
    ("VMCreateArgs", "vm_create.command_line_args"),
    ("VMUpdateArgs", "vm_update.command_line_args"),
    # Arbitrary Docker Compose: privileged containers, host bind mounts, host networking.
    ("AppCreateArgs", "app_create.custom_compose_config"),
    ("AppCreateArgs", "app_create.custom_compose_config_string"),
    ("AppUpdateArgs", "update.custom_compose_config"),
    ("AppUpdateArgs", "update.custom_compose_config_string"),
    # Raw rclone / restic argv, run as root.
    ("CloudSyncCreateArgs", "cloud_sync_create.args"),
    ("CloudSyncUpdateArgs", "cloud_sync_update.args"),
    ("CloudSyncListDirectoryArgs", "cloud_sync_ls.args"),
    ("CloudSyncSyncOnetimeArgs", "cloud_sync_sync_onetime.args"),
    ("CloudBackupCreateArgs", "cloud_backup.args"),
    ("CloudBackupUpdateArgs", "data.args"),
}
"""Every `FullAdmin` field of the current API, as ``(args model, the attribute its error is reported under)``.

`smb.update`, `sharing.smb.*` and the cloud tasks' `pre_script` / `post_script` are deliberately absent: those
predate the marker and are still enforced by their own checks in `plugins/smb.py` and `plugins/cloud/crud.py`.
"""


@pytest.fixture(scope="module")
def current_api_package():
    api_dir = pathlib.Path(middlewared.api.__file__).parent
    with os.scandir(api_dir) as sdir:
        versions = sorted(d.name for d in sdir if d.is_dir() and d.name.startswith("v"))

    return importlib.import_module(f"middlewared.api.{versions[-1]}")


@pytest.fixture(scope="module")
def marked_fields(current_api_package):
    """``{args model name: {dotted path, ...}}`` for every args model that declares `FullAdmin` field(s)."""
    result = {}
    for name in dir(current_api_package):
        model = getattr(current_api_package, name)
        if not (isinstance(model, type) and issubclass(model, BaseModel) and name.endswith("Args")):
            continue

        # Walk the whole args model, not just its payload: a method free to put its payload anywhere in its
        # parameter list is exactly the kind this test exists to catch.
        if paths := {".".join(field.path) for field in full_admin_fields(model)}:
            result[name] = paths

    return result


@pytest.fixture(scope="module")
def api_method_consumers():
    """``{args model name: [(location, function name, enforces itself), ...]}`` for every `@api_method`."""
    package_root = pathlib.Path(middlewared.__file__).parent
    result = {}
    for path in sorted(package_root.rglob("*.py")):
        if "pytest" in path.relative_to(package_root).parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for model in _accepts_models(node):
                location = f"{path.relative_to(package_root)}:{node.lineno} {node.name}"
                result.setdefault(model, []).append((location, node.name, _calls_helper(node)))

    return result


def _accepts_models(node):
    """The args model name of each ``@api_method(Model, ...)`` decorating ``node``."""
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or _bare_name(decorator.func) != "api_method":
            continue

        if decorator.args and (name := _bare_name(decorator.args[0])):
            yield name


def _calls_helper(node):
    """Whether ``node``'s body calls the enforcement helper."""
    return any(isinstance(call, ast.Call) and _bare_name(call.func) == ENFORCEMENT_HELPER for call in ast.walk(node))


def _bare_name(node):
    if isinstance(node, ast.Subscript):
        node = node.value

    return getattr(node, "id", None) or getattr(node, "attr", None)


def test_every_marked_field_is_enforced(marked_fields, api_method_consumers):
    """No API method may declare a `FullAdmin` field that nothing checks."""
    errors = []
    for model, paths in sorted(marked_fields.items()):
        if not (consumers := api_method_consumers.get(model)):
            errors.append(
                AssertionError(
                    f"{model} declares FullAdmin field(s) {sorted(paths)} but no @api_method accepts it. Either the "
                    f"model is dead and the marker is pointless, or it is reached some other way and nothing enforces "
                    f"the marker."
                )
            )
            continue

        for location, name, enforces in consumers:
            if name in WRAPPED_METHODS or enforces:
                continue

            errors.append(
                AssertionError(
                    f"{location} accepts {model}, which declares FullAdmin field(s) {sorted(paths)}, but it is neither "
                    f"a {'/'.join(sorted(WRAPPED_METHODS))} (which CRUDService and ConfigService check before calling) "
                    f"nor does it call {ENFORCEMENT_HELPER}. As written, the marker on those fields does nothing."
                )
            )

    if errors:
        raise ExceptionGroup("Unenforced FullAdmin field(s)", errors)


def test_marked_fields_match_the_inventory(marked_fields):
    """The set of `FullAdmin` fields is pinned, so that gaining or losing one is a reviewable change."""
    found = {(model, path) for model, paths in marked_fields.items() for path in paths}

    assert found == INVENTORY, (
        f"added: {sorted(found - INVENTORY)}, removed: {sorted(INVENTORY - found)}. Update INVENTORY once the "
        f"change is intended -- and, when removing a marker, confirm the field can no longer hand a caller a "
        f"capability their role does not already grant."
    )
