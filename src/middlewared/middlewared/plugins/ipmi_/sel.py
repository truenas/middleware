from subprocess import run

from middlewared.api import api_method
from middlewared.api.current import (
    IpmiSelClearArgs,
    IpmiSelClearResult,
    IpmiSelElistEntry,
    IpmiSelInfoArgs,
    IpmiSelInfoResult,
)
from middlewared.service import filterable_api_method, job, Service
from middlewared.utils.filter_list import filter_list
from middlewared.service_exception import CallError

SEL_LOCK = 'sel_lock'


def get_sel_data(data):
    cmd = ['ipmi-sel']
    if data == 'elist':
        cmd.extend(['-v', '--no-header-output', '--comma-separated-output', '--non-abbreviated-units'])
    elif data == 'info':
        cmd.extend(['--info'])
    else:
        raise ValueError(f'Invalid value: {data!r}')

    rv = []
    cp = run(cmd, capture_output=True)
    if cp.returncode == 0 and cp.stdout:
        rv = cp.stdout.decode().split('\n')

    return rv


class IpmiSelService(Service):

    class Config:
        namespace = 'ipmi.sel'
        cli_namespace = 'service.ipmi.sel'

    @filterable_api_method(item=IpmiSelElistEntry, roles=['IPMI_READ'])
    @job(lock=SEL_LOCK, lock_queue_size=1, transient=True)
    def elist(self, job, filters, options):
        """Query IPMI System Event Log (SEL) extended list"""
        rv = []
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv

        job.set_progress(78, 'Enumerating extended event log info')
        for line in get_sel_data('elist'):
            if (values := line.strip().split(',')) and len(values) == 7:
                rv.append({
                    'id': values[0].strip(),
                    'date': values[1].strip(),
                    'time': values[2].strip(),
                    'name': values[3].strip(),
                    'type': values[4].strip(),
                    'event_direction': values[5].strip(),
                    'event': values[6].strip(),
                })

        job.set_progress(100, 'Parsing extended event log complete')
        return filter_list(rv, filters, options)

    @api_method(
        IpmiSelInfoArgs,
        IpmiSelInfoResult,
        roles=['IPMI_READ']
    )
    @job(lock=SEL_LOCK, lock_queue_size=1, transient=True)
    def info(self, job):
        """Query General information about the IPMI System Event Log"""
        rv = {}
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv

        job.set_progress(78, 'Enumerating general extended event log info')
        for line in get_sel_data('info'):
            if (values := line.strip().split(':')) and len(values) == 2:
                entry, value = values
                rv[entry.strip().replace(' ', '_').lower()] = value.strip()

        job.set_progress(100, 'Parsing general extended event log complete')
        return rv

    @api_method(
        IpmiSelClearArgs,
        IpmiSelClearResult,
        roles=['IPMI_WRITE'],
    )
    @job(lock=SEL_LOCK, lock_queue_size=1)
    def clear(self, job):
        if self.middleware.call_sync('ipmi.is_loaded'):
            cp = run(['ipmi-sel', '--clear'], capture_output=True)
            if cp.returncode:
                raise CallError(cp.stderr.decode().strip() or f'Unexpected failure with returncode: {cp.returncode!r}')
