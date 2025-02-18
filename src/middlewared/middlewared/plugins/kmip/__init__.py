# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

async def initialize_kmip_keys(middleware):
    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_keys')


async def __event_system_ready(middleware, event_type, args):
    await initialize_kmip_keys(middleware)


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'kmip', 'KMIP')
    middleware.event_subscribe('system.ready', __event_system_ready)
    if await middleware.call('system.ready'):
        await initialize_kmip_keys(middleware)
