from subprocess import run

from middlewared.service import job, Service, filterable, filterable_returns
from middlewared.utils import filter_list
from middlewared.schema import accepts, returns, Dict
from middlewared.service_exception import CallError

SEL_LOCK = 'sel_lock'


def get_sel_data(data):
    cmd = ['ipmi-sel']
    if data == 'elist':
        cmd.extend(['--comma-separated-output', '--non-abbreviated-units'])
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

    @filterable
    @filterable_returns(Dict('ipmi_elist', additional_attrs=True))
    @job(lock=SEL_LOCK, lock_queue_size=1)
    def elist(self, job, filters, options):
        """Query IPMI System Event Log (SEL) extended list"""
        rv = []
        job.set_progress(78, 'Enumerating extended event log info')
        for line in get_sel_data('elist'):
            if (values := line.strip().split(',')) and len(values) == 6:
                rv.append({
                    'id': values[0].strip(),
                    'date': values[1].strip(),
                    'time': values[2].strip(),
                    'name': values[3].strip(),
                    'type': values[4].strip(),
                    'event': values[5].strip(),
                })

        job.set_progress(100, 'Parsing extended event log complete')
        return filter_list(rv, filters, options)

    @accepts()
    @returns(Dict('ipmi_sel_info', additional_attrs=True))
    @job(lock=SEL_LOCK, lock_queue_size=1)
    def info(self, job):
        """Query General information about the IPMI System Event Log"""
        rv = {}
        job.set_progress(78, 'Enumerating general extended event log info')
        for line in get_sel_data('info'):
            if (values := line.strip().split(':')) and len(values) == 2:
                entry, value = values
                rv[entry.strip().replace(' ', '_').lower()] = value.strip()

        job.set_progress(100, 'Parsing general extended event log complete')
        return rv

    @accepts()
    @returns()
    @job(lock=SEL_LOCK, lock_queue_size=1)
    def clear(self, job):
        cp = run(['ipmi-sel', '--clear'], check_output=True)
        if cp.returncode:
            raise CallError(cp.stderr.decode().strip() or f'Unexpected failure with returncode: {cp.returncode!r}')
