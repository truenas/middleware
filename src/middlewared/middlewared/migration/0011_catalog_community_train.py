from typing import TYPE_CHECKING
from middlewared.plugins.catalog.utils import COMMUNITY_TRAIN, OFFICIAL_LABEL
if TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: 'Middleware'):
    config = await middleware.call2(middleware.services.catalog.config)
    if COMMUNITY_TRAIN not in config.preferred_trains:
        await middleware.call(
            'datastore.update', 'services.catalog', OFFICIAL_LABEL, {
                'preferred_trains': [COMMUNITY_TRAIN] + config.preferred_trains,
            },
        )
    await middleware.call2(middleware.services.catalog.update_train_for_enterprise)
