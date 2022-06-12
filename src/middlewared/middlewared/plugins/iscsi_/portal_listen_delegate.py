from middlewared.common.listen import ListenDelegate
from middlewared.service import ServiceChangeMixin


class ISCSIPortalListenDelegate(ListenDelegate, ServiceChangeMixin):
    def __init__(self, middleware):
        self.middleware = middleware

    async def get_listen_state(self, ips):
        return await self.middleware.call(
            'datastore.query', 'services.iscsitargetportalip', [['ip', 'in', ips]], {'prefix': 'iscsi_target_portalip_'}
        )

    async def set_listen_state(self, state):
        for row in state:
            await self.middleware.call(
                'datastore.update', 'services.iscsitargetportalip', row['id'],
                {'ip': row['ip']}, {'prefix': 'iscsi_target_portalip_'}
            )

        await self._service_change('iscsitarget', 'reload')

    async def listens_on(self, state, ip):
        return any(row['ip'] == ip for row in state)

    async def reset_listens(self, state):
        for row in state:
            await self.middleware.call(
                'datastore.update', 'services.iscsitargetportalip', row['id'],
                {'ip': '0.0.0.0'}, {'prefix': 'iscsi_target_portalip_'}
            )

        await self._service_change('iscsitarget', 'reload')

    async def repr(self, state):
        return {'type': 'SERVICE', 'service': 'iscsi.portal'}



async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        ISCSIPortalListenDelegate(middleware),
    )
