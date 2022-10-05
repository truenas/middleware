import contextlib
import ssl
import time
import types

import pytest
from pyVim import connect, task as VimTask
from pyVmomi import vim, vmodl

from middlewared.test.integration.assets.nfs import nfs_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.assets.vmware import vmware
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.string import random_string

import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ip

try:
    from config import (
        VCENTER_HOSTNAME,
        VCENTER_USERNAME,
        VCENTER_PASSWORD,
        VCENTER_DATACENTER,
        VCENTER_ESX_HOST,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason='vCenter credential are missing in config.py')


@contextlib.contextmanager
def vcenter_connection():
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    ssl_context.verify_mode = ssl.CERT_NONE
    si = connect.SmartConnect(
        host=VCENTER_HOSTNAME,
        user=VCENTER_USERNAME,
        pwd=VCENTER_PASSWORD,
        sslContext=ssl_context,
    )

    try:
        yield si
    finally:
        connect.Disconnect(si)


@contextlib.contextmanager
def datastore(si):
    content = si.RetrieveContent()

    for datacenter in content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.Datacenter],
        True,
    ).view:
        if datacenter.name == VCENTER_DATACENTER:
            break
    else:
        raise RuntimeError(f"Datacenter {VCENTER_DATACENTER} not found")

    for host in content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.HostSystem],
        True,
    ).view:
        if host.name == VCENTER_ESX_HOST:
            break
    else:
        raise RuntimeError(f"ESX host {VCENTER_ESX_HOST} not found")

    with dataset("vm") as ds:
        with nfs_share(ds) as share:
            ssh(f"chmod 777 /mnt/{ds}")

            datastore_name = random_string()

            datastore = host.configManager.datastoreSystem.CreateNasDatastore(
                vim.host.NasVolume.Specification(
                    remoteHost=ip,
                    remotePath=share["path"],
                    localPath=datastore_name,
                    accessMode=vim.host.MountInfo.AccessMode.readWrite,
                    type=vim.host.FileSystemVolume.FileSystemType.NFS
                )
            )

            try:
                yield types.SimpleNamespace(
                    datacenter=datacenter,
                    host=host,
                    name=datastore_name,
                    dataset=ds,
                )
            finally:
                VimTask.WaitForTask(datastore.Destroy_Task())


@contextlib.contextmanager
def vm(si, datastore):
    content = si.RetrieveContent()

    vm_name = random_string()

    config = vim.vm.ConfigSpec()
    config.memoryMB = 2048
    config.guestId = "ubuntu64Guest"
    config.name = vm_name
    config.numCPUs = 1
    config.files = vim.vm.FileInfo()
    config.files.vmPathName = f"[{datastore.name}]"

    VimTask.WaitForTask(datastore.datacenter.vmFolder.CreateVm(
        config,
        pool=datastore.host.parent.resourcePool,
        host=datastore.host,
    ))

    for vm in content.viewManager.CreateContainerView(
        content.rootFolder,
        [vim.VirtualMachine],
        True,
    ).view:
        if vm.name == vm_name:
            break
    else:
        raise RuntimeError("Created VM not found")

    try:
        VimTask.WaitForTask(vm.PowerOn())

        try:
            yield vm_name
        finally:
            VimTask.WaitForTask(vm.PowerOff())
    finally:
        VimTask.WaitForTask(vm.Destroy_Task())


def test_vmware():
    with vcenter_connection() as si:
        with datastore(si) as ds:
            with vm(si, ds):
                result = call(
                    "vmware.match_datastores_with_datasets",
                    {
                        "hostname": VCENTER_HOSTNAME,
                        "username": VCENTER_USERNAME,
                        "password": VCENTER_PASSWORD,
                    },
                )
                for rds in result["datastores"]:
                    if (
                        rds["name"] == ds.name and
                        rds["description"] == f"NFS mount '/mnt/{ds.dataset}' on {ip}" and
                        rds["filesystems"] == [ds.dataset]
                    ):
                        break
                else:
                    assert False, result

                with vmware({
                    "datastore": ds.name,
                    "filesystem": ds.dataset,
                    "hostname": VCENTER_HOSTNAME,
                    "username": VCENTER_USERNAME,
                    "password": VCENTER_PASSWORD,
                }):
                    with snapshot_task({
                        "dataset": ds.dataset,
                        "recursive": False,
                        "lifetime_value": 1,
                        "lifetime_unit": "DAY",
                        "naming_schema": "%Y%m%d%H%M",
                    }) as task:
                        call("pool.snapshottask.run", task["id"])

                        for i in range(60):
                            time.sleep(1)
                            snapshots = call("zfs.snapshot.query", [["dataset", "=", ds.dataset]])
                            if snapshots:
                                break
                        else:
                            assert False

                        assert snapshots[0]["properties"]["freenas:vmsynced"]["value"] == "Y"
