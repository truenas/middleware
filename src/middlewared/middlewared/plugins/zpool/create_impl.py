from truenas_pylibzfs import VDevType, create_vdev_spec

from middlewared.plugins.pool_.utils import ZPOOL_CACHE_FILE

__all__ = (
    "DraidConfigError",
    "assemble_create_pool_vdev_kwargs",
    "build_fs_properties",
    "build_pool_properties",
    "build_vdev_spec",
    "convert_topology_to_vdevs",
    "resolve_draid_ndata",
    "validate_vdev_layout",
)

# Standard OpenZFS dRAID limits. truenas_pylibzfs does not expose these, so they
# are mirrored here from the kernel module's vdev_draid limits.
VDEV_DRAID_MAX_CHILDREN = 255
VDEV_DRAID_MAXPARITY = 3
VDEV_DRAID_MAX_SPARES = 100

# Minimum disk count per vdev type for a valid data/special/dedup vdev.
MIN_DISKS_PER_VDEV = {
    "STRIPE": 1,
    "MIRROR": 2,
    "DRAID1": 2,
    "DRAID2": 3,
    "DRAID3": 4,
    "RAIDZ1": 3,
    "RAIDZ2": 4,
    "RAIDZ3": 5,
}

# Maps a converted-topology root to the matching create_pool() keyword argument.
ROOT_TO_KWARG = {
    "DATA": "storage_vdevs",
    "CACHE": "cache_vdevs",
    "LOG": "log_vdevs",
    "SPECIAL": "special_vdevs",
    "DEDUP": "dedup_vdevs",
    "SPARE": "spare_vdevs",
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


def convert_topology_to_vdevs(topology: dict) -> tuple[dict, list[dict]]:
    """Flatten an API topology into a disk map and a vdev list.

    Returns ``(disks, vdevs)`` where ``disks`` maps each disk name to ``{'vdev':
    <devices list>}`` and ``vdevs`` is a list of ``{'root', 'type', 'devices'}``
    entries (plus dRAID parameters where relevant). The ``devices`` list of each
    vdev is shared with ``disks`` so that ``pool.format_disks`` can populate it
    in place with the formatted ``/dev/<gptid>`` paths.
    """
    disks: dict[str, dict] = {}
    vdevs: list[dict] = []
    for root in ("data", "cache", "log", "special", "dedup"):
        for t_vdev in topology.get(root) or []:
            devices: list[str] = []
            vdev = {"root": root.upper(), "type": t_vdev["type"], "devices": devices}
            if t_vdev["type"].startswith("DRAID"):
                vdev["draid_data_disks"] = t_vdev["draid_data_disks"]
                vdev["draid_spare_disks"] = t_vdev["draid_spare_disks"]
            vdevs.append(vdev)
            for disk in t_vdev["disks"]:
                disks[disk] = {"vdev": devices}

    if topology.get("spares"):
        devices = []
        vdevs.append({"root": "SPARE", "type": "STRIPE", "devices": devices})
        for disk in topology["spares"]:
            disks[disk] = {"vdev": devices}

    return disks, vdevs


def validate_vdev_layout(topology: dict) -> list[tuple[str, str]]:
    """Validate vdev counts, type homogeneity, dRAID config, and cache/log arity.

    Returns a list of ``(field, message)`` pairs (relative to the topology) so the
    caller can attach them to its ``ValidationErrors`` before any disks are touched.
    """
    errors: list[tuple[str, str]] = []
    for root in ("data", "special", "dedup"):
        last_type = None
        for i, vdev in enumerate(topology.get(root) or []):
            numdisks = len(vdev["disks"])
            mindisks = MIN_DISKS_PER_VDEV[vdev["type"]]
            if numdisks < mindisks:
                errors.append(
                    (f"topology.{root}.{i}.disks", f"You need at least {mindisks} disk(s) for this vdev type.")
                )

            if vdev["type"].startswith("DRAID"):
                try:
                    resolve_draid_ndata(
                        numdisks, int(vdev["type"][-1]), vdev.get("draid_spare_disks", 0), vdev.get("draid_data_disks")
                    )
                except DraidConfigError as e:
                    errors.append((f"topology.{root}.{i}.type", str(e)))

            if last_type and last_type != vdev["type"]:
                errors.append((
                    f"topology.{root}.{i}.type",
                    f"You are not allowed to create a pool with different {root} vdev types "
                    f"({last_type} and {vdev['type']}).",
                ))
            last_type = vdev["type"]

    for root in ("cache", "log"):
        value = topology.get(root)
        if value and len(value) > 1:
            errors.append((f"topology.{root}", f"Only one row for the virtual device of type {root} is allowed."))

    return errors


def build_vdev_spec(vdev: dict):
    """Translate a single converted-topology vdev into ``struct_vdev_create_spec``.

    STRIPE vdevs expand to a flat ``list`` of leaf specs (no parent vdev); every
    other type returns a single parent spec wrapping its leaf children. dRAID
    encodes its config in the spec name as ``"<ndata>d:<nspares>s"``.
    """
    leaves = [create_vdev_spec(vdev_type=VDevType.DISK, name=dev) for dev in vdev["devices"]]
    vtype = vdev["type"]
    if vtype == "STRIPE":
        return leaves
    if vtype.startswith("DRAID"):
        nspares = vdev["draid_spare_disks"]
        ndata = resolve_draid_ndata(len(leaves), int(vtype[-1]), nspares, vdev["draid_data_disks"])
        return create_vdev_spec(vdev_type=getattr(VDevType, vtype), name=f"{ndata}d:{nspares}s", children=leaves)
    return create_vdev_spec(vdev_type=getattr(VDevType, vtype), children=leaves)


def assemble_create_pool_vdev_kwargs(vdevs: list[dict]) -> dict[str, list]:
    """Group converted-topology vdevs into the six create_pool() vdev keyword args."""
    kwargs: dict[str, list] = {}
    for vdev in vdevs:
        spec = build_vdev_spec(vdev)
        bucket = kwargs.setdefault(ROOT_TO_KWARG[vdev["root"]], [])
        if isinstance(spec, list):
            bucket.extend(spec)
        else:
            bucket.append(spec)
    return kwargs


def build_pool_properties(dedup_table_quota: str | None) -> dict[str, str]:
    """Pool-level (zpool) properties for create_pool().

    ``feature@lz4_compress`` is intentionally omitted: it is not a valid ``zpool``
    property key and create_pool() enables every supported feature by default.
    """
    props = {
        "altroot": "/mnt",
        "cachefile": ZPOOL_CACHE_FILE,
        "failmode": "continue",
        "autoexpand": "on",
        "ashift": "12",
    }
    if dedup_table_quota is not None:
        props["dedup_table_quota"] = dedup_table_quota
    return props


def build_fs_properties(name: str, deduplication: str | None, checksum: str | None, has_draid: bool) -> dict[str, str]:
    """Root-filesystem properties for create_pool().

    The ``zpool`` namespace does not create encrypted pool roots, so no encryption
    properties are emitted here.
    """
    props = {
        "atime": "off",
        "acltype": "posix",
        "aclinherit": "discard",
        "aclmode": "discard",
        "compression": "lz4",
        "xattr": "sa",
        "mountpoint": f"/{name}",
    }
    if has_draid:
        props["recordsize"] = "1M"
    if deduplication:
        props["dedup"] = deduplication.lower()
    if checksum is not None:
        props["checksum"] = checksum.lower()
    return props
