from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from middlewared.api.current import ZpoolEntry, ZpoolQuery

from .query_impl import query_impl as _raw_query

if TYPE_CHECKING:
    from middlewared.service import ServiceContext
    from middlewared.utils.types import EventType

__all__ = ("EVENT_PROPERTIES", "offline_entries", "query", "query_impl", "send_change_event")

# Properties baked into every emitted `zpool.query` event so that subscribers
# receive a Pool-shaped payload without having to round-trip another call.
EVENT_PROPERTIES = (
    "class_normal_used",
    "class_normal_available",
    "class_normal_usable",
    "class_special_used",
    "class_special_available",
    "class_special_usable",
    "autotrim",
    "dedup_table_size",
    "dedup_table_quota",
)


def query_impl(tls: Any, data: ZpoolQuery) -> list[dict[str, Any]]:
    return _raw_query(tls.lzh, data.model_dump())


def offline_entries(
    context: ServiceContext, db_pools: dict[str, dict[str, Any]], offline_names: Iterable[str]
) -> list[dict[str, Any]]:
    """Build OFFLINE ZpoolEntry dicts for pools not currently imported.

    For pools flagged as all-SED in the database, checks whether locked
    SED disks may explain the import failure and sets status_code and
    status_detail accordingly. The SED check is performed at most once
    per call and reused across all offline all-SED pools.
    """
    entries = []
    sed_cache: dict[str, Any] = {}
    for name in offline_names:
        pool_info = db_pools.get(name, {})
        status_code = None
        status_detail = None

        if pool_info.get("all_sed"):
            if not sed_cache:
                sed_enabled = context.middleware.call_sync("system.sed_enabled")
                locked_sed_disks = set()
                if sed_enabled:
                    for disk in context.middleware.call_sync(
                        "disk.query",
                        [["sed_status", "=", "LOCKED"]],
                        {"extra": {"sed_status": True}},
                    ):
                        locked_sed_disks.add(disk["name"])
                sed_cache.update(
                    {
                        "sed_enabled": sed_enabled,
                        "locked_sed_disks": locked_sed_disks,
                    }
                )

            if sed_cache["sed_enabled"] and sed_cache["locked_sed_disks"]:
                status_code = "LOCKED_SED_DISKS"
                status_detail = (
                    "Pool might have failed to import because of "
                    f"{', '.join(sed_cache['locked_sed_disks'])!r} SED disk(s) being locked"
                )

        entries.append(
            {
                "id": pool_info["id"] if pool_info else None,
                "name": name,
                "guid": str(pool_info["guid"]) if pool_info else "0",
                "status": "OFFLINE",
                "healthy": False,
                "warning": False,
                "status_code": status_code,
                "status_detail": status_detail,
                "is_upgraded": None,
                "all_sed": pool_info.get("all_sed"),
            }
        )
    return entries


def query(context: ServiceContext, data: ZpoolQuery) -> list[ZpoolEntry]:
    boot_pool_name = context.call_sync2(context.s.boot.pool_name)
    requested_names = data.pool_names

    db_pools = {}
    pool_names = []
    for p in context.middleware.call_sync("datastore.query", "storage.volume", [], {"prefix": "vol_"}):
        if requested_names is None or p["name"] in requested_names:
            db_pools[p["name"]] = p
            pool_names.append(p["name"])

    # Boot pool is never in the database but can be explicitly requested.
    if requested_names is not None and boot_pool_name in requested_names:
        pool_names.append(boot_pool_name)

    results = context.call_sync2(context.s.zpool.query_impl, data.model_copy(update={"pool_names": pool_names}))
    for entry in results:
        entry.update({"id": None, "all_sed": None})
        db_entry = db_pools.get(entry["name"])
        if db_entry is not None:
            entry.update({"id": db_entry["id"], "all_sed": db_entry["all_sed"]})

    imported_names = {p["name"] for p in results}
    offline_names = [name for name in pool_names if name not in imported_names]
    results.extend(offline_entries(context, db_pools, offline_names))

    return [ZpoolEntry(**pool) for pool in results]


def send_change_event(context: ServiceContext, pool_name: str, event_type: EventType = "CHANGED") -> None:
    """Emit a ``zpool.query`` event with a Pool-shaped payload.

    Re-queries ``zpool.query`` with topology, scan, and the standard
    property set so subscribers receive the same fields they would
    from a direct call. No-ops when the pool is not in the database
    (boot pool, or a pool that has been exported between the trigger
    and the emit).
    """
    pools = context.call_sync2(
        context.s.zpool.query,
        ZpoolQuery(pool_names=[pool_name], topology=True, scan=True, properties=list(EVENT_PROPERTIES)),
    )
    if not pools:
        return
    pool = pools[0].model_dump()
    if pool["id"] is None:
        return
    context.middleware.send_event("zpool.query", event_type, id=pool["id"], fields=pool)
