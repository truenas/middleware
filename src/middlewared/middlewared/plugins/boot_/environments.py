import datetime
import errno
import json
import os
import subprocess

from middlewared.api import api_method
from middlewared.utils.mount import statmount
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
    ZFSResourceQuery,
)
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service import filterable_api_method, Service, private
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils.filter_list import filter_list
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
        rv = list()
        bp_name = self.middleware.call_sync('boot.pool_name')
        for i in self.call_sync2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[f"{bp_name}/ROOT"],
                get_children=True,
                properties=["used", "creation"],
                get_user_properties=True,
            )
        ):
            if i["name"].count("/") == 2:
                # boot-pool/ROOT/25.04.1
                # and not boot-pool/ROOT/25.04.1/blah
                rv.append(i)
        return rv, bp_name

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

    @filterable_api_method(item=BootEnvironmentEntry, roles=['BOOT_ENV_READ'])
    def query(self, filters, options):
        results = list()
        try:
            info, bp_name = self.zfs_get_props()
        except Exception:
            return results

        active_be = statmount(path='/')['mount_source']
        activated_be = self.middleware.call_sync(
            "zfs.pool.query", [["name", "=", bp_name]], {"get": True}
        )["properties"]["bootfs"]["value"]
        for i in info:
            props = i["properties"]
            results.append(
                {
                    "id": os.path.basename(i["name"]),
                    "dataset": i["name"],
                    "active": active_be == i["name"],
                    "activated": activated_be == i["name"],
                    "created": datetime.datetime.utcfromtimestamp(
                        props["creation"]["value"]
                    ),
                    "used_bytes": props["used"]["value"],
                    "used": format_size(props["used"]["value"]),
                    "keep": i["user_properties"].get("zectl:keep") == "True",
                    "can_activate": i["user_properties"].get("truenas:kernel_version") != "-",
                }
            )
        return filter_list(results, filters, options)

    @api_method(BootEnvironmentActivateArgs, BootEnvironmentActivateResult, roles=["BOOT_ENV_WRITE"])
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
            return self.query([["id", "=", data["id"]]], {"get": True})

    @api_method(BootEnvironmentCloneArgs, BootEnvironmentCloneResult, roles=['BOOT_ENV_WRITE'])
    def clone(self, data):
        be = self.validate_be("boot.environment.clone", data["id"])
        self.validate_be("boot.environment.clone", data["target"], should_exist=False)
        run_zectl_cmd(["create", "-r", "-e", be["dataset"], data["target"]])
        return self.query([["id", "=", data["target"]]], {"get": True})

    @api_method(BootEnvironmentDestroyArgs, BootEnvironmentDestroyResult, roles=['BOOT_ENV_WRITE'])
    def destroy(self, data):
        if self.validate_be("boot.environment.destroy", data["id"])["active"]:
            raise ValidationError(
                "boot.environment.destroy",
                "Deleting the active boot environment is not allowed",
            )
        run_zectl_cmd(["destroy", data["id"]])

    @api_method(BootEnvironmentKeepArgs, BootEnvironmentKeepResult, roles=['BOOT_ENV_WRITE'])
    def keep(self, data):
        self.middleware.call_sync(
            "pool.dataset.update_impl",
            UpdateImplArgs(
                name=self.validate_be("boot.environment.keep", data["id"])["dataset"],
                uprops={"zectl:keep": str(data["value"])},
            )
        )
        return self.query([["id", "=", data["id"]]], {"get": True})


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
