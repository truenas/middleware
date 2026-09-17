"""Pure helpers for zpool.create: topology translation and property flattening.

Nothing here touches middleware or the libzfs handle except ``validate_impl``
and ``create_impl``, the two calls into ``truenas_pylibzfs``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_pylibzfs import ValidationError, VDevType, ZFSException, ZFSProperty, ZPOOLProperty, create_vdev_spec

from .exceptions import ZpoolCreateException, ZpoolCreateRejected

if TYPE_CHECKING:
    from truenas_pylibzfs import libzfs_types

    from middlewared.api.base import BaseModel
    from middlewared.api.current import ZpoolCreateTopology

__all__ = (
    "MIN_DISKS_PER_VDEV",
    "assemble_create_pool_vdev_kwargs",
    "binding_location",
    "build_vdev_spec",
    "convert_topology_to_vdevs",
    "create_impl",
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

# create_pool() arguments that are request fields of the same name
DIRECT_ARGUMENTS = ("name", "properties", "filesystem_properties")


def binding_location(argument: str, index: int | None) -> str | None:
    """Translate where the binding located a refusal into a ``zpool.create`` attribute suffix.

    A vdev argument maps to its topology root, with the vdev position when the
    binding knew it; ``name`` and the two property arguments map to themselves;
    anything else (an argument the request does not expose) maps to None.
    """
    if (root := KWARG_TO_ROOT.get(argument)) is not None:
        return f"topology.{root}" if index is None else f"topology.{root}.{index}"
    if argument in DIRECT_ARGUMENTS:
        return argument
    return None


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
    as ``"<ndata>d:<nspares>s"``, or ``"<nspares>s"`` when the data disks per
    group are left to the ``zpool create`` default; the binding validates it as
    the spec is built.
    """
    leaves = [create_vdev_spec(vdev_type=VDevType.DISK, name=name) for name in vdev[names]]
    vtype = vdev["type"]
    if vtype == "disk":
        return leaves
    if vtype.startswith("draid"):
        nspares = vdev["draid_spare_disks"]
        ndata = vdev["draid_data_disks"]
        config = f"{nspares}s" if ndata is None else f"{ndata}d:{nspares}s"
        return create_vdev_spec(vdev_type=VDevType(vtype), name=config, children=leaves)
    return create_vdev_spec(vdev_type=VDevType(vtype), children=leaves)


def assemble_create_pool_vdev_kwargs(vdevs: list[dict[str, Any]], names: str = "devices") -> dict[str, list[Any]]:
    """Group converted-topology vdevs into the six create_pool() vdev keyword args.

    A vdev the binding refuses to build (a dRAID configuration its disks
    cannot satisfy) raises ``ZpoolCreateRejected`` located at that vdev.
    """
    kwargs: dict[str, list[Any]] = {}
    position = {root: 0 for root in ROOT_TO_KWARG}
    for vdev in vdevs:
        root = vdev["root"]
        try:
            spec = build_vdev_spec(vdev, names)
        except ValidationError as e:
            location = f"topology.{root}" if root in ("cache", "spares") else f"topology.{root}.{position[root]}"
            raise ZpoolCreateRejected(location, e.reason) from e
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
    binding judges everything ``zpool_create()`` would before its ioctl: the
    vdev types each root accepts, the dRAID configuration, the pool name, the
    property names and values and, unless ``force``, the topology policy. A
    refusal raises ``ZpoolCreateRejected`` located where the binding placed it.
    """
    specs = assemble_create_pool_vdev_kwargs(vdevs, "disks")
    try:
        _create_pool(lzh, name, specs, properties, filesystem_properties, force, dry_run=True)
    except ValidationError as e:
        raise ZpoolCreateRejected(binding_location(e.argument, e.index), e.reason) from e


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
