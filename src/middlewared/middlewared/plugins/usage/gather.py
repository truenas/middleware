"""Collection of the anonymous usage statistics that get submitted to TrueNAS.

Adding a new statistic
----------------------

Write a module-level function named ``gather_<name>`` and decorate it with
``@gather_stat``::

    @gather_stat
    def gather_my_feature(service: Service, context: GatherContext) -> dict[str, Any]:
        return {'my_feature': ...}

The decorator registers it in ``GATHER_FUNCS`` keyed by its function name, and
``gather()`` picks it up automatically — there is nothing else to wire up. The
function name doubles as its ``restrict_usage`` token (the optional allow-list
passed to ``gather()``).

A stat function receives the owning ``service`` (use ``service.call2`` for typed
in-process calls, ``service.middleware.call`` for the rest) and the shared
``context`` built once by ``get_gather_context``, and must return a ``dict`` that
is merged into the submitted payload. It may be either ``def`` or ``async def``:
``gather()`` runs in a worker thread, so synchronous functions run inline while
coroutines are driven on the event loop via ``service.middleware.run_coroutine``.
"""

from __future__ import annotations

from collections import defaultdict
import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from middlewared.api.current import VMDisplayDevice, ZFSResourceQuery
from middlewared.plugins.zfs_.utils import path_to_dataset_impl

if TYPE_CHECKING:
    from middlewared.service import Service

logger = logging.getLogger(__name__)

GatherContext = dict[str, Any]
GatherFunc = Callable[["Service", GatherContext], "dict[str, Any] | Coroutine[Any, Any, dict[str, Any]]"]

GATHER_FUNCS: dict[str, GatherFunc] = {}


def gather_stat(func: GatherFunc) -> GatherFunc:
    GATHER_FUNCS[func.__name__] = func
    return func


def get_gather_context(service: Service) -> GatherContext:
    context: GatherContext = {
        "network": service.middleware.call_sync("interface.query"),
        "root_datasets": {},
        "total_capacity": 0,
        "datasets_total_size": 0,
        "datasets_total_size_recursive": 0,
        "zvols_total_size": 0,
        "zvols": [],
        "datasets": {},
        "total_datasets": 0,
        "total_zvols": 0,
        "services": [],
    }
    for i in service.middleware.call_sync("datastore.query", "services.services", [], {"prefix": "srv_"}):
        context["services"].append({"name": i["service"], "enabled": i["enable"]})

    qry_ops = ZFSResourceQuery(get_children=True, exclude_internal_paths=False)
    for ds in service.call_sync2(service.s.zfs.resource.query_impl, qry_ops):
        if ds["name"] == ds["pool"]:
            context["root_datasets"][ds["pool"]] = ds
            context["total_datasets"] += 1
            context["datasets_total_size"] += ds["properties"]["used"]["value"]
            context["total_capacity"] += ds["properties"]["used"]["value"] + ds["properties"]["available"]["value"]
        elif ds["type"] == "VOLUME":
            context["zvols"].append(ds)
            context["total_zvols"] += 1
            context["zvols_total_size"] += ds["properties"]["used"]["value"]
        elif ds["type"] == "FILESYSTEM":
            context["total_datasets"] += 1

        context["datasets_total_size_recursive"] += ds["properties"]["used"]["value"]
        context["datasets"][ds["name"]] = ds

    return context


def gather(service: Service, restrict_usage: list[str] | None = None) -> dict[str, Any]:
    context = get_gather_context(service)
    restrict = set(restrict_usage or [])

    usage_stats: dict[str, Any] = {}
    for name, func in GATHER_FUNCS.items():
        if restrict and name not in restrict:
            continue

        try:
            result = func(service, context)
            stats = result if isinstance(result, dict) else service.middleware.run_coroutine(result)
        except Exception:
            logger.error("Failed to gather stats from %r", name, exc_info=True)
        else:
            usage_stats.update(stats)

    return usage_stats


@gather_stat
def gather_total_capacity(service: Service, context: GatherContext) -> dict[str, Any]:
    return {"total_capacity": context["total_capacity"]}


@gather_stat
def gather_backup_data(service: Service, context: GatherContext) -> dict[str, Any]:
    backed = {"cloudsync": 0, "rsynctask": 0, "zfs_replication": 0, "total_size": 0}
    filters = [["enabled", "=", True], ["direction", "=", "PUSH"], ["locked", "=", False]]
    tasks_found: dict[str, set[str]] = {"cloudsync": set(), "rsynctask": set()}
    for namespace in ("cloudsync", "rsynctask"):
        opposite_namespace = "rsynctask" if namespace == "cloudsync" else "cloudsync"
        for task in service.middleware.call_sync(f"{namespace}.query", filters):
            # FIXME: rsynctask is typesafe and returns Pydantic models while cloudsync still
            # returns dicts. Once cloudsync is converted, drop this branch and call both via
            # call_sync2 with attribute access.
            path = task["path"] if isinstance(task, dict) else task.path
            try:
                task_ds = path_to_dataset_impl(path)
            except Exception:
                logger.error("Failed mapping path %r to dataset", path, exc_info=True)
            else:
                if (task_ds and task_ds in context["datasets"]) and (task_ds not in tasks_found[namespace]):
                    # dataset for the task was found, and exists and hasn't already been calculated
                    size = context["datasets"][task_ds]["properties"]["used"]["value"]
                    backed[namespace] += size
                    if task_ds not in tasks_found[opposite_namespace]:
                        # a "task" (cloudsync, rsync, replication) can be backing up the same dataset
                        # so we don't want to add to the total backed up size because it will report
                        # an inflated number. Instead we only add to the total backed up size when it's
                        # a dataset only being backed up by a singular cloud/rsync/replication task
                        backed["total_size"] += size

                    tasks_found[namespace].add(task_ds)

    repls_found: set[str] = set()
    filters = [["enabled", "=", True], ["transport", "!=", "LOCAL"], ["direction", "=", "PUSH"]]
    for task in service.call_sync2(service.s.replication.query, filters):
        for source in filter(lambda s: s in context["datasets"] and s not in repls_found, task.source_datasets):
            size = context["datasets"][source]["properties"]["used"]["value"]
            backed["zfs_replication"] += size
            repls_found.add(source)
            if source not in tasks_found["cloudsync"] and source not in tasks_found["rsynctask"]:
                # a "task" (cloudsync, rsync, replication) can be backing up the same dataset
                # so we don't want to add to the total backed up size because it will report
                # an inflated number. Instead we only add to the total backed up size when it's
                # a dataset only being backed up by a singular cloud/rsync/replication task
                backed["total_size"] += size

    return {
        "data_backup_stats": backed,
        "data_without_backup_size": context["datasets_total_size_recursive"] - backed["total_size"],
    }


@gather_stat
async def gather_applications(service: Service, context: GatherContext) -> dict[str, Any]:
    # We want to retrieve following information
    # 1) No of installed apps
    # 2) catalog items with versions installed
    # 3) List of docker images
    output: dict[str, Any] = {
        "apps": 0,
        # train -> item -> versions
        "catalog_items": defaultdict(lambda: defaultdict(lambda: defaultdict(int))),
        "docker_images": set(),
    }
    apps = await service.call2(service.s.app.query)
    output["apps"] = len(apps)
    for app in apps:
        output["catalog_items"][app.metadata["train"]][app.metadata["name"]][app.version] += 1

    for image in await service.call2(service.s.app.image.query):
        output["docker_images"].update(image.repo_tags)

    output["docker_images"] = list(output["docker_images"])
    return output


@gather_stat
def gather_filesystem_usage(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "datasets": {"total_size": context["datasets_total_size"]},
        "zvols": {"total_size": context["zvols_total_size"]},
    }


@gather_stat
async def gather_ha_stats(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "ha_licensed": await service.middleware.call("failover.licensed"),
    }


@gather_stat
async def gather_directory_service_stats(service: Service, context: GatherContext) -> dict[str, Any]:
    status = await service.middleware.call("directoryservices.status")
    return {"directory_services": status}


@gather_stat
async def gather_cloud_services(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "cloud_services": list(
            {
                t["credentials"]["provider"]["type"]
                for t in await service.middleware.call(
                    "cloudsync.query", [["enabled", "=", True]], {"select": ["enabled", "credentials"]}
                )
            }
        )
    }


@gather_stat
async def gather_hardware(service: Service, context: GatherContext) -> dict[str, Any]:
    network = context["network"]
    cpu = await service.middleware.call("system.cpu_info")

    return {
        "hardware": {
            "cpus": cpu["core_count"],
            "cpu_model": cpu["cpu_model"],
            "memory": (await service.middleware.call("system.mem_info"))["physmem_size"],
            "nics": len(network),
            "disks": [{k: disk[k]} for disk in await service.middleware.call("disk.query") for k in ["model"]],
        }
    }


@gather_stat
async def gather_method_stats(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "method_stats": service.middleware.external_method_calls,
    }


@gather_stat
async def gather_network(service: Service, context: GatherContext) -> dict[str, Any]:
    info: dict[str, Any] = {"network": {"bridges": [], "lags": [], "phys": [], "vlans": []}}
    for i in context["network"]:
        if i["type"] == "BRIDGE":
            info["network"]["bridges"].append({"members": i["bridge_members"], "mtu": i["mtu"]})
        elif i["type"] == "LINK_AGGREGATION":
            info["network"]["lags"].append({"members": i["lag_ports"], "mtu": i["mtu"], "type": i["lag_protocol"]})
        elif i["type"] == "PHYSICAL":
            info["network"]["phys"].append(
                {"name": i["name"], "mtu": i["mtu"], "dhcp": i["ipv4_dhcp"], "slaac": i["ipv6_auto"]}
            )
        elif i["type"] == "VLAN":
            info["network"]["vlans"].append(
                {"mtu": i["mtu"], "name": i["name"], "tag": i["vlan_tag"], "pcp": i["vlan_pcp"]}
            )

    return info


@gather_stat
async def gather_system_version(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "platform": f"TrueNAS-{await service.middleware.call('system.product_type')}",
        "version": await service.middleware.call("system.version"),
        "is_vendored": await service.call2(service.s.system.vendor.is_vendored),
        "vendor_name": await service.call2(service.s.system.vendor.name),
        "is_virtualized": await service.call2(service.s.hardware.virtualization.is_virtualized),
        "hypervisor": await service.call2(service.s.hardware.virtualization.variant),
    }


@gather_stat
async def gather_system(service: Service, context: GatherContext) -> dict[str, Any]:
    return {
        "system_hash": await service.middleware.call("system.host_id"),
        "usage_version": 1,
        "system": [
            {
                "users": await service.middleware.call("user.query", [["local", "=", True]], {"count": True}),
                "zvols": context["total_zvols"],
                "datasets": context["total_datasets"],
            }
        ],
    }


@gather_stat
async def gather_pools(service: Service, context: GatherContext) -> dict[str, Any]:
    total_raw_capacity = 0  # zpool list -p -o size summed together of all zpools
    pool_list = []
    for p in filter(lambda x: x["status"] != "OFFLINE", await service.middleware.call("pool.query")):
        total_raw_capacity += p["size"]
        disks = vdevs = 0
        _type = "UNKNOWN"
        if (pd := context["root_datasets"].get(p["name"])) is None:
            logger.error("%r is missing, skipping collection", p["name"])
            continue
        else:
            pd = pd["properties"]

        for d in p["topology"]["data"]:
            if not d.get("path"):
                vdevs += 1
                _type = d["type"]
                disks += len(d["children"])
            else:
                disks += 1
                _type = "STRIPE"

        pool_list.append(
            {
                "capacity": pd["used"]["value"] + pd["available"]["value"],
                "disks": disks,
                "l2arc": bool(p["topology"]["cache"]),
                "type": _type.lower(),
                "usedbydataset": pd["usedbydataset"]["value"],
                "usedbysnapshots": pd["usedbysnapshots"]["value"],
                "usedbychildren": pd["usedbychildren"]["value"],
                "usedbyrefreservation": pd["usedbyrefreservation"]["value"],
                "vdevs": vdevs if vdevs else disks,
                "zil": bool(p["topology"]["log"]),
            }
        )

    return {"pools": pool_list, "total_raw_capacity": total_raw_capacity}


@gather_stat
async def gather_services(service: Service, context: GatherContext) -> dict[str, Any]:
    return {"services": context["services"]}


@gather_stat
async def gather_nfs(service: Service, context: GatherContext) -> dict[str, Any]:
    num_clients = await service.middleware.call("nfs.client_count")
    nfs_config = await service.middleware.call("nfs.config")
    return {
        "NFS": {
            "enabled_protocols": nfs_config["protocols"],
            "kerberos": nfs_config["v4_krb_enabled"],
            "num_clients": num_clients,
        }
    }


@gather_stat
async def gather_ftp(service: Service, context: GatherContext) -> dict[str, Any]:
    """Gather number of FTP connection info."""
    ftp_config = await service.call2(service.s.ftp.config)
    num_conn = await service.call2(service.s.ftp.connection_count)

    return {"FTP": {"connections_allowed": ftp_config.clients * ftp_config.ipconnections, "num_connections": num_conn}}


@gather_stat
async def gather_sharing(service: Service, context: GatherContext) -> dict[str, Any]:
    sharing_list = []
    for share_service in {"iscsi", "nfs", "smb"}:
        service_upper = share_service.upper()
        namespace = f"sharing.{share_service}" if share_service != "iscsi" else "iscsi.targetextent"
        for s in await service.middleware.call(f"{namespace}.query"):
            if share_service == "smb":
                sharing_list.append({"type": service_upper, "purpose": s["purpose"]})
            elif share_service == "nfs":
                sharing_list.append({"type": service_upper, "readonly": s["ro"]})
            elif share_service == "iscsi":
                tar = await service.middleware.call("iscsi.target.query", [("id", "=", s["target"])], {"get": True})
                ext = await service.middleware.call(
                    "iscsi.extent.query",
                    [("id", "=", s["extent"])],
                    {
                        "get": True,
                        "extra": {"retrieve_locked_info": False},
                    },
                )
                sharing_list.append(
                    {
                        "type": service_upper,
                        "mode": tar["mode"],
                        "groups": tar["groups"],
                        "iscsi_type": ext["type"],
                        "filesize": ext["filesize"],
                        "blocksize": ext["blocksize"],
                        "pblocksize": ext["pblocksize"],
                        "avail_threshold": ext["avail_threshold"],
                        "insecure_tpc": ext["insecure_tpc"],
                        "xen": ext["xen"],
                        "rpm": ext["rpm"],
                        "readonly": ext["ro"],
                        "legacy": ext["vendor"] == "FreeBSD",
                        "vendor": ext["vendor"],
                    }
                )

    return {"shares": sharing_list}


@gather_stat
async def gather_vms(service: Service, context: GatherContext) -> dict[str, Any]:
    vms = []
    for v in await service.call2(service.s.vm.query):
        nics = disks = 0
        display_list = []
        for d in v.devices:
            if d.attributes.dtype == "NIC":
                nics += 1
            elif d.attributes.dtype == "DISK":
                disks += 1
            elif isinstance(d.attributes, VMDisplayDevice):
                display_list.append(
                    {
                        "wait": d.attributes.wait,
                        "resolution": d.attributes.resolution,
                        "web": d.attributes.web,
                    }
                )

        vms.append(
            {
                "bootloader": v.bootloader,
                "memory": v.memory,
                "vcpus": v.vcpus,
                "autostart": v.autostart,
                "time": v.time,
                "nics": nics,
                "disks": disks,
                "display_devices": len(display_list),
                "display_devices_configs": display_list,
            }
        )

    return {"vms": vms}
