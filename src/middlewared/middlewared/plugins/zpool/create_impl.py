"""Pure helpers for zpool.create: topology translation and property flattening.

Nothing here touches middleware or the libzfs handle except ``create_impl``,
which is the single call into ``truenas_pylibzfs``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_pylibzfs import VDevType, ZFSException, ZFSProperty, ZPOOLProperty, create_vdev_spec

from .exceptions import ZpoolCreateException

if TYPE_CHECKING:
    from truenas_pylibzfs import libzfs_types

    from middlewared.api.base import BaseModel
    from middlewared.api.current import ZPoolCreateTopology

__all__ = (
    "DraidConfigError",
    "MAX_DISKS_PER_VDEV",
    "MIN_DISKS_PER_VDEV",
    "VDEV_PARITY",
    "assemble_create_pool_vdev_kwargs",
    "build_vdev_spec",
    "convert_topology_to_vdevs",
    "create_impl",
    "properties_to_zfs",
    "resolve_draid_ndata",
)

# Standard OpenZFS dRAID limits. truenas_pylibzfs does not expose these, so they
# are mirrored here from the kernel module's vdev_draid limits.
VDEV_DRAID_MAX_CHILDREN = 255
VDEV_DRAID_MAXPARITY = 3
VDEV_DRAID_MAX_SPARES = 100

MIN_DISKS_PER_VDEV = {
    "disk": 1,
    "mirror": 2,
    "draid1": 2,
    "draid2": 3,
    "draid3": 4,
    "raidz1": 3,
    "raidz2": 4,
    "raidz3": 5,
}

# Maximum width of the redundant data vdev types, mirroring truenas_pylibzfs's
# PYLIBZFS_MAX_MIRROR_WIDTH and PYLIBZFS_MAX_RAIDZ_WIDTH; keep in sync with the
# binding. disk is uncapped and dRAID is bounded by resolve_draid_ndata().
MAX_DISKS_PER_VDEV = {
    "mirror": 4,
    "raidz1": 15,
    "raidz2": 15,
    "raidz3": 15,
}

VDEV_PARITY = {
    "disk": 0,
    "mirror": 1,
    "raidz1": 1,
    "raidz2": 2,
    "raidz3": 3,
    "draid1": 1,
    "draid2": 2,
    "draid3": 3,
}

# Maps a converted-topology root to the matching create_pool() keyword argument.
ROOT_TO_KWARG = {
    "data": "storage_vdevs",
    "cache": "cache_vdevs",
    "log": "log_vdevs",
    "special": "special_vdevs",
    "dedup": "dedup_vdevs",
    "spares": "spare_vdevs",
}


class DraidConfigError(ValueError):
    """Raised when a dRAID vdev configuration is invalid."""


def resolve_draid_ndata(children: int, parity: int, nspares: int, ndata: int | None) -> int:
    """Resolve and validate the number of dRAID data disks per redundancy group.

    Mirrors the historical py-libzfs ``validate_draid_configuration`` behavior: when
    ``ndata`` is unset it defaults to all remaining disks, capped at 8. Raises
    ``DraidConfigError`` when the configuration cannot be satisfied.
    """
    if ndata is None:
        if children > nspares + parity:
            ndata = min(children - nspares - parity, 8)
        else:
            raise DraidConfigError(
                f"Requested number of distributed spares {nspares} and parity level {parity} "
                "leaves no disks available for data."
            )

    if ndata == 0 or (ndata + parity) > (children - nspares):
        raise DraidConfigError(
            f"Requested number of dRAID data disks per group {ndata} is too high; at most "
            f"{children - nspares - parity} disks are available for data."
        )
    if parity == 0 or parity > VDEV_DRAID_MAXPARITY:
        raise DraidConfigError(f"Invalid dRAID parity level {parity}; must be between 1 and {VDEV_DRAID_MAXPARITY}.")
    if nspares > VDEV_DRAID_MAX_SPARES or nspares > (children - (ndata + parity)):
        raise DraidConfigError(f"Invalid number of dRAID spares {nspares}. Additional disks would be required.")
    if children < (ndata + parity + nspares):
        raise DraidConfigError(
            f"{children} disks were provided, but at least {ndata + parity + nspares} disks are required "
            "for this configuration."
        )
    if children > VDEV_DRAID_MAX_CHILDREN:
        raise DraidConfigError(
            f"{children} disks were provided, but dRAID supports at most {VDEV_DRAID_MAX_CHILDREN} disks."
        )
    return ndata


def convert_topology_to_vdevs(topology: ZPoolCreateTopology) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Flatten an API topology into a disk map and a vdev list.

    Returns ``(disks, vdevs)`` where ``disks`` maps each disk name to ``{'vdev':
    <devices list>}`` and ``vdevs`` is a list of ``{'root', 'type', 'devices'}``
    entries (plus dRAID parameters where relevant). The ``devices`` list of each
    vdev is shared with ``disks`` so that ``pool.format_disks`` can populate it
    in place with the formatted ``/dev/<gptid>`` paths. ``cache`` and ``spares``
    are plain disk lists in the API and become one ``disk`` vdev each here.
    """
    disks: dict[str, Any] = {}
    vdevs: list[dict[str, Any]] = []
    for root in ("data", "log", "special", "dedup"):
        for t_vdev in getattr(topology, root):
            devices: list[str] = []
            vdev: dict[str, Any] = {"root": root, "type": t_vdev.type, "devices": devices}
            if t_vdev.type.startswith("draid"):
                vdev["draid_data_disks"] = t_vdev.draid_data_disks
                vdev["draid_spare_disks"] = t_vdev.draid_spare_disks
            vdevs.append(vdev)
            for disk in t_vdev.disks:
                disks[disk] = {"vdev": devices}

    for root in ("cache", "spares"):
        if leaves := getattr(topology, root):
            devices = []
            vdevs.append({"root": root, "type": "disk", "devices": devices})
            for disk in leaves:
                disks[disk] = {"vdev": devices}

    return disks, vdevs


def build_vdev_spec(vdev: dict[str, Any]) -> Any:
    """Translate a single converted-topology vdev into ``struct_vdev_create_spec``.

    ``disk`` vdevs expand to a flat ``list`` of leaf specs (no parent vdev); every
    other type returns a single parent spec wrapping its leaf children. dRAID
    encodes its config in the spec name as ``"<ndata>d:<nspares>s"``.
    """
    leaves = [create_vdev_spec(vdev_type=VDevType.DISK, name=dev) for dev in vdev["devices"]]
    vtype = vdev["type"]
    if vtype == "disk":
        return leaves
    if vtype.startswith("draid"):
        nspares = vdev["draid_spare_disks"]
        ndata = resolve_draid_ndata(len(leaves), int(vtype[-1]), nspares, vdev["draid_data_disks"])
        return create_vdev_spec(vdev_type=VDevType(vtype), name=f"{ndata}d:{nspares}s", children=leaves)
    return create_vdev_spec(vdev_type=VDevType(vtype), children=leaves)


def assemble_create_pool_vdev_kwargs(vdevs: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Group converted-topology vdevs into the six create_pool() vdev keyword args."""
    kwargs: dict[str, list[Any]] = {}
    for vdev in vdevs:
        spec = build_vdev_spec(vdev)
        bucket = kwargs.setdefault(ROOT_TO_KWARG[vdev["root"]], [])
        if isinstance(spec, list):
            bucket.extend(spec)
        else:
            bucket.append(spec)
    return kwargs


def properties_to_zfs(properties: BaseModel) -> dict[str, str]:
    """Flatten a properties model into the ``{name: value}`` strings ZFS takes.

    A field left as None is not sent so ZFS applies its own default.
    """
    return {name: str(value) for name, value in properties.model_dump(exclude_none=True).items()}


def create_impl(
    lzh: libzfs_types.ZFS,
    name: str,
    vdevs: list[dict[str, Any]],
    properties: dict[str, str],
    filesystem_properties: dict[str, str],
    force: bool,
) -> None:
    """Create the pool through ``truenas_pylibzfs``.

    This is the only step that touches the libzfs handle. ``vdevs`` is the
    converted topology whose device lists ``pool.format_disks`` has populated
    with ``/dev/<gptid>`` paths; the property dicts are keyed by native name;
    ``force`` skips the binding's topology policy.
    """
    specs = assemble_create_pool_vdev_kwargs(vdevs)
    try:
        lzh.create_pool(
            name=name,
            storage_vdevs=specs.get("storage_vdevs", []),
            cache_vdevs=specs.get("cache_vdevs"),
            log_vdevs=specs.get("log_vdevs"),
            special_vdevs=specs.get("special_vdevs"),
            dedup_vdevs=specs.get("dedup_vdevs"),
            spare_vdevs=specs.get("spare_vdevs"),
            properties={ZPOOLProperty[k.upper()]: v for k, v in properties.items()},
            filesystem_properties={ZFSProperty[k.upper()]: v for k, v in filesystem_properties.items()},
            force=force,
        )
    except ZFSException as e:
        raise ZpoolCreateException(name, str(e)) from e
