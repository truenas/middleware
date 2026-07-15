from __future__ import annotations

import typing


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    """Relocate migrated containers' origin images out of legacy ``.ix-virt``.

    Systems that ran the incus->container migration before the origin-relocation
    fix have containers under ``.truenas_containers`` whose ``origin`` snapshot
    still lives inside ``.ix-virt``; deleting ``.ix-virt`` would cascade into
    them and destroy them. Move each such origin image into the native images
    tree so that dependency is severed.

    Fresh upgraders have no ``container.container`` rows yet when this runs (the
    incus migration fires later, on ``system.ready``), so this is a no-op for
    them - they are handled inside the migration itself. Best-effort: any row
    that cannot be repaired is logged and skipped.
    """
    for container in await middleware.call("datastore.query", "container.container"):
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
