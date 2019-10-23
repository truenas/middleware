import enum
from middlewared.schema import accepts
from middlewared.service import Service, private
from samba.dcerpc.messaging import MSG_WINBIND_OFFLINE, MSG_WINBIND_ONLINE


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = MSG_WINBIND_OFFLINE
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = MSG_WINBIND_ONLINE


class DSType(enum.Enum):
    AD = 'activedirectory'
    LDAP = 'ldap'
    NIS = 'nis'


class DirectoryServices(Service):
    class Config:
        service = "directoryservices"

    @accepts()
    async def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        try:
            return (await self.middleware.call('cache.get', 'DS_State'))
        except KeyError:
            ds_state = {}
            for srv in DSType:
                try:
                    res = await self.middleware.call(f'{srv.value}.started')
                    ds_state[srv.value] = DSStatus.HEALTHY.name if res else DSStatus.DISABLED.name
                except Exception:
                    ds_state[srv.value] = DSStatus.FAULTED.name

            await self.middleware.call('cache.put', 'DS_STATE', ds_state)
            return ds_state

    @private
    async def set_state(self, new):
        ds_state = {
            'activedirectory': DSStatus.DISABLED.name,
            'ldap': DSStatus.DISABLED.name,
            'nis': DSStatus.DISABLED.name
        }
        ds_state.update(await self.get_state())
        ds_state.update(new)
        self.middleware.send_event('directoryservices.status', 'CHANGED', fields=ds_state)
        return await self.middleware.call('cache.put', 'DS_STATE', ds_state)


def setup(middleware):
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
