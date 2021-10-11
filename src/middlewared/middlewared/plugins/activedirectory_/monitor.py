import json
import os
import threading
import middlewared.utils.osc as osc

from middlewared.plugins.smb import SMBCmd, SMBPath, WBCErr
from middlewared.plugins.directoryservices import DSStatus
from middlewared.service import Service


class WBStatusThread(threading.Thread):
    def __init__(self, **kwargs):
        super(WBStatusThread, self).__init__()
        self.setDaemon(True)
        self.middleware = kwargs.get('middleware')
        self.logger = self.middleware.logger
        self.finished = threading.Event()
        self.state = DSStatus.FAULTED.value

    def parse_msg(self, data):
        if data == str(DSStatus.LEAVING.value):
            return

        try:
            m = json.loads(data)
        except json.decoder.JSONDecodeError:
            self.logger.debug("Unable to decode winbind status message: "
                              "%s", data)
            return

        new_state = self.state

        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.debug('Ignoring winbind message for disabled AD service: [%s]', m)
            return

        try:
            new_state = DSStatus(m['winbind_message']).value
        except Exception as e:
            self.logger.debug('Received invalid winbind status message [%s]: %s', m, e)
            return

        if m['domain_name_netbios'] != self.middleware.call_sync('smb.config')['workgroup']:
            self.logger.debug(
                'Domain [%s] changed state to %s',
                m['domain_name_netbios'],
                DSStatus(m['winbind_message']).name
            )
            return

        if self.state != new_state:
            self.logger.debug(
                'State of domain [%s] transistioned to [%s]',
                m['forest_name'], DSStatus(m['winbind_message'])
            )
            self.middleware.call_sync('activedirectory.set_state', DSStatus(m['winbind_message']))
            if new_state == DSStatus.FAULTED.value:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )
            else:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "ActiveDirectoryDomainOffline",
                    {"domain": m["domain_name_netbios"]}
                )

        self.state = new_state

    def read_messages(self):
        while not self.finished.is_set():
            with open(f'{SMBPath.RUNDIR.platform()}/.wb_fifo') as f:
                data = f.read()
                for msg in data.splitlines():
                    self.parse_msg(msg)

        self.logger.debug('exiting winbind messaging thread')

    def run(self):
        osc.set_thread_name('ad_monitor_thread')
        try:
            self.read_messages()
        except Exception as e:
            self.logger.debug('Failed to run monitor thread %s', e, exc_info=True)

    def setup(self):
        if not os.path.exists(f'{SMBPath.RUNDIR.platform()}/.wb_fifo'):
            os.mkfifo(f'{SMBPath.RUNDIR.platform()}/.wb_fifo')

    def cancel(self):
        """
        Write to named pipe to unblock open() in thread and exit cleanly.
        """
        self.finished.set()
        with open(f'{SMBPath.RUNDIR.platform()}/.wb_fifo', 'w') as f:
            f.write(str(DSStatus.LEAVING.value))


class ADMonitorService(Service):
    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(ADMonitorService, self).__init__(*args, **kwargs)
        self.thread = None
        self.initialized = False
        self.lock = threading.Lock()

    def start(self):
        if not self.middleware.call_sync('activedirectory.config')['enable']:
            self.logger.trace('Active directory is disabled. Exiting AD monitoring.')
            return

        with self.lock:
            if self.initialized:
                return

            thread = WBStatusThread(
                middleware=self.middleware,
            )
            thread.setup()
            self.thread = thread
            thread.start()
            self.initialized = True

    def stop(self):
        thread = self.thread
        if thread is None:
            return

        thread.cancel()
        self.thread = None

        with self.lock:
            self.initialized = False

    def restart(self):
        self.stop()
        self.start()


async def setup(middleware):
    """
    During initial boot let smb_configure script start monitoring once samba's
    rundir is created.
    """
    if await middleware.call('system.ready'):
        await middleware.call('admonitor.start')
