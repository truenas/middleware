import glob
import os
import subprocess

from .rrd_utils import RRDBase

from middlewared.utils import osc


class CPUPlugin(RRDBase):

    plugin = 'aggregation-cpu-sum'
    title = 'CPU Usage'
    vertical_label = '%CPU'
    stacked = True

    def get_defs(self, identifier):
        if self.middleware.call_sync('reporting.config')['cpu_in_percentage']:
            type = 'gauge' if osc.IS_FREEBSD else 'percent'  # FIXME: backport our patches to SCALE
            cpu_idle = os.path.join(self.base_path, f'{type}-idle.rrd')
            cpu_nice = os.path.join(self.base_path, f'{type}-nice.rrd')
            cpu_user = os.path.join(self.base_path, f'{type}-user.rrd')
            cpu_system = os.path.join(self.base_path, f'{type}-system.rrd')
            cpu_interrupt = os.path.join(self.base_path, f'{type}-interrupt.rrd')

            args = [
                f'DEF:idle={cpu_idle}:value:AVERAGE',
                f'DEF:nice={cpu_nice}:value:AVERAGE',
                f'DEF:user={cpu_user}:value:AVERAGE',
                f'DEF:system={cpu_system}:value:AVERAGE',
                f'DEF:interrupt={cpu_interrupt}:value:AVERAGE',
                'XPORT:interrupt:interrupt',
                'XPORT:system:system',
                'XPORT:user:user',
                'XPORT:nice:nice',
                'XPORT:idle:idle',
            ]

            return args

        else:
            cpu_idle = os.path.join(self.base_path, 'cpu-idle.rrd')
            cpu_nice = os.path.join(self.base_path, 'cpu-nice.rrd')
            cpu_user = os.path.join(self.base_path, 'cpu-user.rrd')
            cpu_system = os.path.join(self.base_path, 'cpu-system.rrd')
            cpu_interrupt = os.path.join(self.base_path, 'cpu-interrupt.rrd')

            args = [
                f'DEF:idle={cpu_idle}:value:AVERAGE',
                f'DEF:nice={cpu_nice}:value:AVERAGE',
                f'DEF:user={cpu_user}:value:AVERAGE',
                f'DEF:system={cpu_system}:value:AVERAGE',
                f'DEF:interrupt={cpu_interrupt}:value:AVERAGE',
                'CDEF:total=idle,nice,user,system,interrupt,+,+,+,+',
                'CDEF:idle_p=idle,total,/,100,*',
                'CDEF:nice_p=nice,total,/,100,*',
                'CDEF:user_p=user,total,/,100,*',
                'CDEF:system_p=system,total,/,100,*',
                'CDEF:interrupt_p=interrupt,total,/,100,*',
                'XPORT:interrupt_p:interrupt',
                'XPORT:system_p:system',
                'XPORT:user_p:user',
                'XPORT:nice_p:nice',
                'XPORT:idle_p:idle',
            ]

            return args


class DiskTempPlugin(RRDBase):

    vertical_label = '\u00b0C'
    rrd_types = (
        ('temperature', 'value', None),
    )

    def get_title(self):
        return 'Disk Temperature {identifier}'

    def get_identifiers(self):
        disks_for_temperature_monitoring = self.middleware.call_sync('disk.disks_for_temperature_monitoring')
        ids = []
        for entry in glob.glob(f'{self._base_path}/disktemp-*'):
            ident = entry.rsplit('-', 1)[-1]
            if ident in disks_for_temperature_monitoring and os.path.exists(os.path.join(entry, 'temperature.rrd')):
                ids.append(ident)
        ids.sort(key=RRDBase._sort_disks)
        return ids


class InterfacePlugin(RRDBase):

    vertical_label = 'Bits/s'
    rrd_types = (
        ('if_octets', 'rx', '%name%,8,*'),
        ('if_octets', 'tx', '%name%,8,*'),
    )
    rrd_data_extra = """
        CDEF:overlap=%name_0%,%name_1%,LT,%name_0%,%name_1%,IF
        XPORT:overlap:overlap
    """

    def get_title(self):
        return 'Interface Traffic ({identifier})'

    def get_identifiers(self):
        ids = []
        ifaces = [i['name'] for i in self.middleware.call_sync('interface.query')]
        for entry in glob.glob(f'{self._base_path}/interface-*'):
            ident = entry.rsplit('-', 1)[-1]
            if ident not in ifaces:
                continue
            if os.path.exists(os.path.join(entry, 'if_octets.rrd')):
                ids.append(ident)
        ids.sort(key=RRDBase._sort_disks)
        return ids


class MemoryPlugin(RRDBase):

    title = 'Physical memory utilization'
    vertical_label = 'Bytes'
    if osc.IS_FREEBSD:
        rrd_types = (
            ('memory-wired', 'value', None),
            ('memory-inactive', 'value', None),
            ('memory-laundry', 'value', None),
            ('memory-active', 'value', None),
            ('memory-free', 'value', None),
        )
        stacked = True
    else:
        rrd_types = (
            ('memory-used', 'value', None),
            ('memory-free', 'value', None),
            ('memory-cached', 'value', None),
            ('memory-buffered', 'value', None),
        )


class LoadPlugin(RRDBase):

    title = 'System Load'
    vertical_label = 'Processes'
    rrd_types = (
        ('load', 'shortterm', None),
        ('load', 'midterm', None),
        ('load', 'longterm', None),
    )


class ProcessesPlugin(RRDBase):

    title = 'Processes'
    vertical_label = 'Processes'
    if osc.IS_FREEBSD:
        rrd_types = (
            ('ps_state-wait', 'value', None),
            ('ps_state-idle', 'value', None),
            ('ps_state-sleeping', 'value', None),
            ('ps_state-running', 'value', None),
            ('ps_state-stopped', 'value', None),
            ('ps_state-zombies', 'value', None),
            ('ps_state-blocked', 'value', None),
        )
    else:
        rrd_types = (
            ('ps_state-sleeping', 'value', None),
            ('ps_state-running', 'value', None),
            ('ps_state-stopped', 'value', None),
            ('ps_state-zombies', 'value', None),
            ('ps_state-blocked', 'value', None),
        )
    stacked = True


class SwapPlugin(RRDBase):

    title = 'Swap Utilization'
    vertical_label = 'Bytes'
    rrd_types = (
        ('swap-used', 'value', None),
        ('swap-free', 'value', None),
    )
    stacked = True


class DFPlugin(RRDBase):

    vertical_label = 'Bytes'
    rrd_types = (
        ('df_complex-free', 'value', None),
        ('df_complex-used', 'value', None),
    )
    stacked = True
    stacked_show_total = True

    def get_title(self):
        return 'Disk space ({identifier})'

    def encode(self, path):
        if path == '/':
            return 'root'
        return path.strip('/').replace('/', '-')

    def get_identifiers(self):
        ids = []
        cp = subprocess.run(['df', '-t', 'zfs'], capture_output=True, text=True)
        for line in cp.stdout.strip().split('\n'):
            entry = line.split()[-1].strip()
            if entry != '/' and not entry.startswith('/mnt'):
                continue
            path = os.path.join(self._base_path, 'df-' + self.encode(entry), 'df_complex-free.rrd')
            if os.path.exists(path):
                ids.append(entry)
        return ids


class UptimePlugin(RRDBase):

    title = 'Uptime'
    vertical_label = 'Days'
    rrd_types = (
        ('uptime', 'value', '%name%,86400,/'),
    )


class DiskPlugin(RRDBase):

    vertical_label = 'Bytes/s'
    rrd_types = (
        ('disk_octets', 'read', None),
        ('disk_octets', 'write', None),
    )

    def get_title(self):
        return 'Disk I/O ({identifier})'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob(f'{self._base_path}/disk-*'):
            ident = entry.split('-', 1)[-1]
            if not os.path.exists(f'/dev/{ident}'):
                continue
            if ident.startswith('pass'):
                continue
            if os.path.exists(os.path.join(entry, 'disk_octets.rrd')):
                ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids


class ARCSizePlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = 'Bytes'
    rrd_types = (
        ('cache_size-arc', 'value', None),
        ('cache_size-L2', 'value', None),
    )

    def get_title(self):
        return 'ARC Size'


class ARCRatioPlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = 'Hits (%)'
    rrd_types = (
        ('cache_ratio-arc', 'value', '%name%,100,*'),
        ('cache_ratio-L2', 'value', '%name%,100,*'),
    )

    def get_title(self):
        return 'ARC Hit Ratio'


class ARCResultPlugin(RRDBase):

    identifier_plugin = False
    plugin = 'zfs_arc'
    vertical_label = 'Requests'
    stacked = True
    stacked_show_total = True

    def get_rrd_types(self, identifier):
        return (
            (f'cache_result-{identifier}-hit', 'value', '%name%,100,*'),
            (f'cache_result-{identifier}-miss', 'value', '%name%,100,*'),
        )

    def get_title(self):
        return 'ARC Requests ({identifier})'

    def get_identifiers(self):
        return ['demand_data', 'demand_metadata', 'prefetch_data', 'prefetch_metadata']
