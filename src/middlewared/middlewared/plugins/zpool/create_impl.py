"""Pure helpers for zpool.create: topology translation and property flattening.

Nothing here touches middleware or the libzfs handle except ``validate_impl``
and ``create_impl``, the two calls into ``truenas_pylibzfs``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from truenas_pylibzfs import VDevType, ZFSException, ZFSProperty, ZPOOLProperty, create_vdev_spec

from .exceptions import ZpoolCreateException, ZpoolTopologyRejected

if TYPE_CHECKING:
    from truenas_pylibzfs import libzfs_types

    from middlewared.api.base import BaseModel
    from middlewared.api.current import ZpoolCreateTopology

__all__ = (
    "MIN_DISKS_PER_VDEV",
    "assemble_create_pool_vdev_kwargs",
    "build_vdev_spec",
    "convert_topology_to_vdevs",
    "create_impl",
    "default_draid_ndata",
    "properties_to_zfs",
    "validate_impl",
)

# TrueNAS asks for more disks per vdev than ZFS itself accepts (a two-disk
# RAIDZ1 is legal but pointless), so this is product policy on top of the
# binding's own minimums rather than a copy of them.
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

DRAID_DEFAULT_NDATA = 8

# Maps a converted-topology root to the matching create_pool() keyword argument.
ROOT_TO_KWARG = {
    "data": "storage_vdevs",
    "cache": "cache_vdevs",
    "log": "log_vdevs",
    "special": "special_vdevs",
    "dedup": "dedup_vdevs",
    "spares": "spare_vdevs",
}
KWARG_TO_ROOT = {kwarg: root for root, kwarg in ROOT_TO_KWARG.items()}

_FORCE_HINT = re.compile(r"(pass|use) force=True to override")


def default_draid_ndata(children: int, parity: int, nspares: int) -> int:
    """Data disks per dRAID redundancy group when the caller leaves it unset.

    Every disk left after parity and spares, capped at 8, as ``zpool create``
    defaults it. Never below 1, so a vdev too small for its parity and spares
    is reported by the binding as short of disks rather than as a zero data
    count.
    """
    return max(min(children - nspares - parity, DRAID_DEFAULT_NDATA), 1)


def convert_topology_to_vdevs(topology: ZpoolCreateTopology) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Flatten an API topology into a disk map and a vdev list.

    Returns ``(disks, vdevs)`` where ``disks`` maps each disk name to ``{'vdev':
    <devices list>}`` and ``vdevs`` is a list of ``{'root', 'type', 'disks',
    'devices'}`` entries (plus dRAID parameters where relevant). ``disks`` holds
    the disk names as requested; the ``devices`` list of each vdev starts empty
    and is shared with ``disks`` so that ``pool.format_disks`` can populate it
    in place with the formatted ``/dev/<gptid>`` paths. ``cache`` and ``spares``
    are plain disk lists in the API and become one ``disk`` vdev each here.
    """
    disks: dict[str, Any] = {}
    vdevs: list[dict[str, Any]] = []
    for root in ("data", "log", "special", "dedup"):
        for t_vdev in getattr(topology, root):
            devices: list[str] = []
            vdev: dict[str, Any] = {"root": root, "type": t_vdev.type, "disks": list(t_vdev.disks), "devices": devices}
            if t_vdev.type.startswith("draid"):
                vdev["draid_data_disks"] = t_vdev.draid_data_disks
                vdev["draid_spare_disks"] = t_vdev.draid_spare_disks
            vdevs.append(vdev)
            for disk in t_vdev.disks:
                disks[disk] = {"vdev": devices}

    for root in ("cache", "spares"):
        if leaves := getattr(topology, root):
            devices = []
            vdevs.append({"root": root, "type": "disk", "disks": list(leaves), "devices": devices})
            for disk in leaves:
                disks[disk] = {"vdev": devices}

    return disks, vdevs


def build_vdev_spec(vdev: dict[str, Any], names: str = "devices") -> Any:
    """Translate a single converted-topology vdev into ``struct_vdev_create_spec``.

    ``names`` picks the list that supplies the leaf names: ``devices`` (the
    formatted partition paths, for creation) or ``disks`` (the disk names, for
    a dry run, which never opens them). ``disk`` vdevs expand to a flat ``list``
    of leaf specs (no parent vdev); every other type returns a single parent
    spec wrapping its leaf children. dRAID encodes its config in the spec name
    as ``"<ndata>d:<nspares>s"``; the binding validates it as the spec is built.
    """
    leaves = [create_vdev_spec(vdev_type=VDevType.DISK, name=name) for name in vdev[names]]
    vtype = vdev["type"]
    if vtype == "disk":
        return leaves
    if vtype.startswith("draid"):
        nspares = vdev["draid_spare_disks"]
        ndata = vdev["draid_data_disks"]
        if ndata is None:
            ndata = default_draid_ndata(len(leaves), int(vtype[-1]), nspares)
        return create_vdev_spec(vdev_type=VDevType(vtype), name=f"{ndata}d:{nspares}s", children=leaves)
    return create_vdev_spec(vdev_type=VDevType(vtype), children=leaves)


def assemble_create_pool_vdev_kwargs(vdevs: list[dict[str, Any]], names: str = "devices") -> dict[str, list[Any]]:
    """Group converted-topology vdevs into the six create_pool() vdev keyword args.

    A vdev the binding refuses to build (a dRAID configuration its disks
    cannot satisfy) raises ``ZpoolTopologyRejected`` located at that vdev.
    """
    kwargs: dict[str, list[Any]] = {}
    position = {root: 0 for root in ROOT_TO_KWARG}
    for vdev in vdevs:
        root = vdev["root"]
        try:
            spec = build_vdev_spec(vdev, names)
        except ValueError as e:
            location = root if root in ("cache", "spares") else f"{root}.{position[root]}"
            raise ZpoolTopologyRejected(location, _strip_context(str(e))) from e
        position[root] += 1
        bucket = kwargs.setdefault(ROOT_TO_KWARG[root], [])
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


def _strip_context(message: str) -> str:
    """Drop the ``<argument>: `` prefix the binding puts on its messages and
    point the force hint at the API field instead of the binding's parameter."""
    _, sep, rest = message.partition(": ")
    return _FORCE_HINT.sub("set force_topology to override", rest if sep else message)


def _create_pool(
    lzh: libzfs_types.ZFS,
    name: str,
    specs: dict[str, list[Any]],
    properties: dict[str, str],
    filesystem_properties: dict[str, str],
    force: bool,
    dry_run: bool,
) -> None:
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
        dry_run=dry_run,
    )


def validate_impl(
    lzh: libzfs_types.ZFS,
    name: str,
    vdevs: list[dict[str, Any]],
    properties: dict[str, str],
    filesystem_properties: dict[str, str],
    force: bool,
) -> None:
    """Run the binding's own checks against the request without creating anything.

    The leaf names are the disk names rather than partition paths, which the
    dry run never opens, so this can run before any disk is formatted. The
    binding judges the vdev types each root accepts, the dRAID configuration,
    the property names and, unless ``force``, the topology policy. A refusal
    raises ``ZpoolTopologyRejected`` located at the topology root the binding
    named, or unlocated when it faulted something else.
    """
    specs = assemble_create_pool_vdev_kwargs(vdevs, "disks")
    try:
        _create_pool(lzh, name, specs, properties, filesystem_properties, force, dry_run=True)
    except ValueError as e:
        kwarg, sep, _ = str(e).partition(": ")
        raise ZpoolTopologyRejected(KWARG_TO_ROOT.get(kwarg) if sep else None, _strip_context(str(e))) from e


def create_impl(
    lzh: libzfs_types.ZFS,
    name: str,
    vdevs: list[dict[str, Any]],
    properties: dict[str, str],
    filesystem_properties: dict[str, str],
    force: bool,
) -> None:
    """Create the pool through ``truenas_pylibzfs``.

    ``vdevs`` is the converted topology whose device lists ``pool.format_disks``
    has populated with ``/dev/<gptid>`` paths; the property dicts are keyed by
    native name; ``force`` skips the binding's topology policy.
    """
    specs = assemble_create_pool_vdev_kwargs(vdevs)
    try:
        _create_pool(lzh, name, specs, properties, filesystem_properties, force, dry_run=False)
    except ZFSException as e:
        raise ZpoolCreateException(name, str(e)) from e
