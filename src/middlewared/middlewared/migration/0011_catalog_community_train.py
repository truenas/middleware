from middlewared.plugins.catalog.utils import COMMUNITY_TRAIN, OFFICIAL_LABEL


async def migrate(middleware):
    config = await middleware.call('catalog.config')
    if COMMUNITY_TRAIN not in config['preferred_trains']:
        await middleware.call(
            'datastore.update', 'services.catalog', OFFICIAL_LABEL, {
                'preferred_trains': [COMMUNITY_TRAIN] + config['preferred_trains'],
            },
        )
    await middleware.call('catalog.update_train_for_enterprise')
