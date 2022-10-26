import enum

from middlewared.service import job, Service


EVENT_FN_MAP = {
    'INIT': 'event_not_implemented',
    'SETUP': 'event_not_implemented',
    'STARTUP': 'event_startup',
    'SHUTDOWN': 'event_not_implemented',
    'MONITOR': 'event_monitor',
    'STARTRECOVERY': 'event_recovery',
    'RECOVERED': 'event_recovery',
    'TAKEIP': 'event_not_implemented',
    'RELEASEIP': 'event_not_implemented',
    'IPREALLOCATED': 'event_ip_reallocated',
}


class CtdbEventType(enum.Enum):
    INIT = enum.auto()
    SETUP = enum.auto()
    STARTUP = enum.auto()
    SHUTDOWN = enum.auto()
    MONITOR = enum.auto()
    STARTRECOVERY = enum.auto()
    RECOVERED = enum.auto()
    TAKEIP = enum.auto()
    RELEASEIP = enum.auto()
    IPREALLOCATED = enum.auto()

    def get_fn(self):
        return EVENT_FN_MAP[self.name]


class CtdbEventService(Service):

    class Config:
        namespace = 'ctdb.event'
        private = True

    def event_ip_reallocated(self, data):
        """
        This is notification only. Not an error. Indicates
        that our public IPs have shifted between nodes.

        We only send out event info from recovery master.
        """
        if not self.middleware.call_sync('ctdb.general.is_rec_master'):
            return

        public_ips = self.middleware.call_sync('ctdb.general.ips')
        self.middleware.send_event(
            'ctdb.status', 'CHANGED', fields={'event': data['event'], 'data': public_ips}
        )

    def event_startup(self, data):
        """
        This event gets triggered when CTDB is starting.
        Expected failure mode is when ctdb_shared_volume isn't properly mounted.
        """
        ev = data.pop('event')
        if data['status'] == 'SUCCESS':
            self.middleware.call_sync('alert.oneshot_delete', 'CtdbInitFail', None)
        else:
            self.middleware.call_sync(
                'alert.oneshot_create',
                'CtdbInitFail',
                {'errmsg': data['reason']}
            )

        self.middleware.send_event(
            'ctdb.status', 'CHANGED', fields={'event': ev, 'data': data}
        )

    def event_monitor(self, data):
        """
        Failure of a ctdb monitored process to start will cause CTDB to enter
        UNHEALTHY state.

        This should occur less than monitor interval. Basically the monitor script
        will only call if the state has changed. Hence we don't need to query alerts here.
        """
        ev = data.pop('event')
        if data['status'] == 'SUCCESS':
            self.middleware.call_sync('alert.oneshot_delete', 'CtdbClusteredService', None)

        else:
            self.middleware.call_sync(
                'alert.oneshot_create',
                'CtdbClusteredService',
                {'errmsg': data['reason']}
            )

        self.middleware.send_event(
            'ctdb.status', 'CHANGED', fields={'event': ev, 'data': data}
        )

    def event_recovery(self, data):
        if not self.middleware.call_sync('ctdb.general.is_rec_master'):
            return

        ev = data.pop('event')
        self.middleware.send_event(
            'ctdb.status', 'CHANGED', fields={'event': ev, 'data': data}
        )

    def event_not_implemented(self, arg_unused):
        raise NotImplementedError()

    @job(lock="event_results", transient=True, lock_queue_size=3)
    def process(self, job, data):
        ev = CtdbEventType[data['event']]
        return getattr(self, ev.get_fn())(data)


def setup(middleware):
    middleware.event_register('ctdb.status', 'Sent on cluster status changes.')
