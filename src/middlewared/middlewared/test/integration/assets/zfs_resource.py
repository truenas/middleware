import contextlib
import errno
import time
from typing import Any

from middlewared.service_exception import ValidationError
from middlewared.test.integration.utils import call

__all__ = ("destroy_zfs_resource", "zfs_resource")

# udev opens a zvol's device node as soon as it appears, so a destroy that
# closely follows a create can fail with EBUSY until udev lets go.
ZVOL_DESTROY_ATTEMPTS = 20
ZVOL_DESTROY_INTERVAL = 0.5


def _holds_a_volume(path: str) -> bool:
    return any(
        resource["type"] == "VOLUME"
        for resource in call(
            "zfs.resource.query",
            {"paths": [path], "get_children": True, "properties": None},
        )
    )


def destroy_zfs_resource(path: str) -> None:
    """Destroy `path` and everything below it.

    Only a tree that holds a volume can be held open by udev, so only that
    case is retried.
    """
    attempts = ZVOL_DESTROY_ATTEMPTS if _holds_a_volume(path) else 1
    for attempt in range(attempts):
        try:
            call("zfs.resource.destroy", {"path": path, "recursive": True})
            return
        except ValidationError as e:
            if e.errno != errno.EBUSY or attempt == attempts - 1:
                raise
            time.sleep(ZVOL_DESTROY_INTERVAL)


def _topmost_missing_ancestor(path: str) -> str | None:
    """Return the highest ancestor of `path` that does not exist yet.

    `create_ancestors` makes more than the path it is given, and destroying
    only that path would leak the ancestors it created.
    """
    parts = path.split("/")
    ancestors = ["/".join(parts[:i]) for i in range(2, len(parts))]
    if not ancestors:
        return None

    existing = {resource["name"] for resource in call("zfs.resource.query", {"paths": ancestors, "properties": None})}
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
