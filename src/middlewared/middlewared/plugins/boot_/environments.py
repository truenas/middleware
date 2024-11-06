import datetime
import errno
import json
import os
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    BootEnvironmentActivateArgs,
    BootEnvironmentActivateResult,
    BootEnvironmentCloneArgs,
    BootEnvironmentCloneResult,
    BootEnvironmentDestroyArgs,
    BootEnvironmentDestroyResult,
    BootEnvironmentEntry,
    BootEnvironmentKeepArgs,
    BootEnvironmentKeepResult,
)
from middlewared.service import filterable_api_method, Service, private
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils import filter_list
from middlewared.utils.size import format_size


def run_zectl_cmd(cmd):
    try:
        cp = subprocess.run(
            ["zectl"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
    except subprocess.CalledProcessError as cpe:
        raise CallError(f"Unexpected error: {cpe.stdout.decode()!r}")
    else:
        return cp.returncode == 0


class BootEnvironmentService(Service):
    class Config:
        namespace = "boot.environment"
        entry = BootEnvironmentEntry
        cli_private = True

    @private
    def zfs_get_props(self):
        zget = "zfs get -r -d 1"
        zget += " truenas:kernel_version,zectl:keep,used,creation"
        bp_name = self.middleware.call_sync("boot.pool_name")
        root = f"{bp_name}/ROOT"
        json_flags = "-j --json-int"  # json format, raw numbers
        try:
            cp = subprocess.run(
                " ".join([zget, root, json_flags]),
                shell=True,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as cpe:
            self.logger.error("getting zfs properties failed: %r", cpe.stderr)
        except Exception:
            self.logger.exception("Unexpected failure getting zfs properties")
        else:
            return json.loads(cp.stdout), bp_name

    @private
    def validate_be(self, schema_name, name, should_exist=True):
        data = self.query([["id", "=", name]])
        if should_exist:
            if not data:
                raise ValidationError(schema_name, f"{name!r} not found")
            else:
                return data[0]
        elif data:
            raise ValidationError(schema_name, f"{name!r} already exists", errno.EEXIST)

    @private
    def promote_current_datasets(self):
        be = self.query([["active", "=", True]], {"get": True})
        be_datasets = subprocess.run(
            f"zfs list -o origin -r {be['dataset']} -j", capture_output=True, shell=True
        )
        for ds, info in json.loads(be_datasets.stdout)["datasets"].items():
            if ds.startswith(f"{be['dataset']}/"):
                origin = info["properties"]["origin"]["value"]
                if origin != "-":
                    self.logger.info(
                        f"Promoting dataset {ds} as it is a clone of {origin}"
                    )
                    try:
                        self.middleware.call_sync("pool.dataset.promote", ds)
                    except Exception:
                        self.logger.exception("Unexpected error promoting %r", ds)

    @filterable_api_method(item=BootEnvironmentEntry)
    def query(self, filters, options):
        results = list()
        try:
            info, bp_name = self.zfs_get_props()
        except TypeError:
            return results

        active_be = self.middleware.call_sync(
            "filesystem.mount_info", [["mountpoint", "=", "/"]], {"get": True}
        )["mount_source"]
        activated_be = self.middleware.call_sync(
            "zfs.pool.query", [["name", "=", bp_name]], {"get": True}
        )["properties"]["bootfs"]["value"]
        for ds_name, ds_info in info["datasets"].items():
            if ds_name == f"{bp_name}/ROOT":
                continue

            props = ds_info["properties"]
            results.append(
                {
                    "id": os.path.basename(ds_name),
                    "dataset": ds_name,
                    "active": active_be == ds_name,
                    "activated": activated_be == ds_name,
                    "created": datetime.datetime.utcfromtimestamp(
                        props["creation"]["value"]
                    ),
                    "used_bytes": props["used"]["value"],
                    "used": format_size(props["used"]["value"]),
                    "keep": props["zectl:keep"]["value"] == "True",
                    "can_activate": props["truenas:kernel_version"]["value"] != "-",
                }
            )

        return filter_list(results, filters, options)

    @api_method(BootEnvironmentActivateArgs, BootEnvironmentActivateResult)
    def activate(self, data):
        info = self.validate_be("boot.environment.activate", data["id"])
        if info["activated"]:
            raise ValidationError(
                "boot.environment.activate", f"{data['id']!r} is already activated"
            )
        elif not info["can_activate"]:
            raise ValidationError(
                "boot.environment.activate", f"{data['id']!r} can not be activated"
            )
        else:
            run_zectl_cmd(["activate", data["id"]])
            return self.query([["id", "=", data["id"]]])

    @api_method(BootEnvironmentCloneArgs, BootEnvironmentCloneResult)
    def clone(self, data):
        be = self.validate_be("boot.environment.clone", data["id"])
        self.validate_be("boot.environment.clone", data["target"], should_exist=False)
        run_zectl_cmd(["create", "-r", "-e", be["dataset"], data["target"]])
        return self.query([["id", "=", data["target"]]])

    @api_method(BootEnvironmentDestroyArgs, BootEnvironmentDestroyResult)
    def destroy(self, data):
        if self.validate_be("boot.environment.destroy", data["id"])["active"]:
            raise ValidationError(
                "boot.environment.destroy",
                "Deleting the active boot environment is not allowed",
            )
        run_zectl_cmd(["destroy", data["id"]])

    @api_method(BootEnvironmentKeepArgs, BootEnvironmentKeepResult)
    def keep(self, data):
        self.middleware.call_sync(
            "zfs.dataset.update",
            self.validate_be("boot.environment.keep", data["id"])["dataset"],
            {
                "properties": {"zectl:keep": {"value": str(data["value"])}},
            },
        )
        return self.query([["id", "=", data["id"]]])


async def setup(middleware):
    if not await middleware.call("system.ready"):
        # Installer clones `/var/log` dataset of the previous install to avoid copying logs. When booting, we must
        # promote the clone to be an independent dataset so that the origin dataset becomes deletable.
        # Only perform this operation on boot time to save a few seconds on middleware restart.
        try:
            await middleware.call("boot.environment.promote_current_datasets")
        except Exception:
            middleware.logger.error(
                "Unhandled exception promoting active boot environment datasets",
                exc_info=True,
            )
