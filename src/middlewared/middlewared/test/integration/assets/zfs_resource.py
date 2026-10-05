import contextlib
from typing import Any

from middlewared.test.integration.utils import call, ssh

__all__ = ("destroy_zfs_resource", "thick_refreservation", "zfs_resource")


def thick_refreservation(path: str) -> int:
    """The refreservation `zfs create -V` gives a volume of the same size and
    block size as `path`: the volsize plus metadata and raidz/draid overhead."""
    ref = f"{path}_ref"
    volsize, volblocksize = ssh(f"zfs get -Hpo value volsize,volblocksize {path}").split()
    ssh(f"zfs create -V {volsize} -o volblocksize={volblocksize} {ref}")
    try:
        return int(ssh(f"zfs get -Hpo value refreservation {ref}"))
    finally:
        ssh(f"zfs destroy {ref}")


def destroy_zfs_resource(path: str) -> None:
    """Destroy `path` and everything below it.

    A resource without children is destroyed non-recursively. Only that path
    retries while udev still holds a new zvol open; the recursive one does not.
    """
    tree = call("zfs.resource.list", {"paths": [path], "get_children": True, "properties": None})
    call("zfs.resource.destroy", {"path": path, "recursive": len(tree) > 1})


def _topmost_missing_ancestor(path: str) -> str | None:
    """Return the highest ancestor of `path` that does not exist yet.

    `create_ancestors` makes more than the path it is given, and destroying
    only that path would leak the ancestors it created.
    """
    parts = path.split("/")
    ancestors = ["/".join(parts[:i]) for i in range(2, len(parts))]
    if not ancestors:
        return None

    existing = {resource["name"] for resource in call("zfs.resource.list", {"paths": ancestors, "properties": None})}
    return next((a for a in ancestors if a not in existing), None)


@contextlib.contextmanager
def zfs_resource(path: str, data: dict[str, Any] | None = None):
    """Create a zfs resource with `zfs.resource.create` and destroy it after.

    Yields the entry that `zfs.resource.create` returned. With
    `create_ancestors`, the ancestors that the create had to make are torn
    down too.
    """
    data = data or {}
    cleanup = path
    if data.get("create_ancestors"):
        cleanup = _topmost_missing_ancestor(path) or path

    entry = call("zfs.resource.create", {"path": path, **data})
    try:
        yield entry
    finally:
        destroy_zfs_resource(cleanup)
