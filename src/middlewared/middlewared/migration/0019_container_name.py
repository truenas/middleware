from __future__ import annotations

import os
import typing


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    for container in await middleware.call('datastore.query', 'container.container'):
        dataset: str = container['dataset']

        # The alembic migration (2026-03-27_16-24_container_name.py) sanitizes
        # container names to conform to RFC 1123 hostname rules (replacing
        # underscores, stripping invalid leading/trailing hyphens, etc.).
        # The dataset column was intentionally left out so we could rename the
        # ZFS datasets here and update the database field accordingly.
        # dataset field is something like the following:
        # dozer/.truenas_containers/containers/test_underscore
        old_name = os.path.basename(dataset)

        # If the dataset basename already matches the current name, no rename is needed.
        if old_name == container['name']:
            continue

        new_dataset = dataset[:dataset.rfind('/') + 1] + container['name']

        middleware.logger.info('Renaming container dataset %r to %r', dataset, new_dataset)
        try:
            await middleware.call2(middleware.services.zfs.resource.rename, dataset, new_dataset)
        except Exception:
            middleware.logger.error(
                'Failed to rename container dataset %r to %r', dataset, new_dataset, exc_info=True,
            )
            # Revert name so it stays in sync with the actual dataset path.
            # The old name may not be RFC-compliant so the container may still
            # have issues starting, but at least name/dataset won't diverge.
            await middleware.call(
                'datastore.update', 'container.container', container['id'], {'name': old_name},
            )
            continue

        await middleware.call(
            'datastore.update', 'container.container', container['id'], {'dataset': new_dataset},
        )
