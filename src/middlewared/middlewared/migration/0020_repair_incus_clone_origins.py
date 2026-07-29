from __future__ import annotations

import typing


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    """Repair what an incus->container migration run on an older build left behind.

    Two things need fixing on those systems:

    Containers under ``.truenas_containers`` whose ``origin`` snapshot still lives
    inside ``.ix-virt``. Deleting ``.ix-virt`` would cascade into them and destroy
    them, so each such origin image is moved into the native images tree.

    The legacy parents' mountpoint. That migration gave ``.ix-virt`` and its
    ``containers`` child an inherited mountpoint and never put it back, so the whole
    legacy tree - children included, since they inherit it - stays mounted under
    ``/mnt/<pool>/.ix-virt`` on every boot with nothing managing it.

    Fresh upgraders have no ``container.container`` rows yet when this runs (the
    incus migration fires later, on ``system.ready``), so this is a no-op for them -
    they are handled inside the migration itself. Best-effort throughout: nothing
    here raises, so a system that cannot be repaired is left as it was rather than
    having the migration re-run on every subsequent boot.
    """
    containers = await middleware.call("datastore.query", "container.container")
    for container in containers:
        dataset = container["dataset"]
        try:
            status = await middleware.call("container.relocate_container_origin", dataset)
        except Exception:
            middleware.logger.error(
                "Failed to relocate origin image for container %r (dataset %r)",
                container["name"],
                dataset,
                exc_info=True,
            )
            continue

        if status == "RELOCATED":
            middleware.logger.info(
                "Relocated origin image for container %r out of .ix-virt",
                container["name"],
            )
        elif status != "ALREADY_SATISFIED":
            middleware.logger.warning(
                "Could not relocate origin image for container %r (dataset %r): %s",
                container["name"],
                dataset,
                status,
            )

    for pool in sorted({container["dataset"].split("/")[0] for container in containers}):
        # Skipped when the pool is not imported or the legacy tree is already gone,
        # so this does not log a failure for every dataset it cannot reach.
        if not await middleware.call("zfs.resource.query", {"paths": [f"{pool}/.ix-virt"], "properties": None}):
            continue

        await middleware.call("container.restore_legacy_parent_mountpoints", pool)
