import glob
import itertools
import os
import re
import subprocess

from .rrd_utils import RRDBase, RRDType


class CPUPlugin(RRDBase):

    plugin = 'aggregation-cpu-sum'
    title = 'CPU Usage'
    vertical_label = '%CPU'
    stacked = True

    def get_rrd_files(self, identifier):
        if self.middleware.call_sync('reporting.config')['cpu_in_percentage']:
            type = 'gauge'
            cpu_idle = os.path.join(self.base_path, f'{type}-idle.rrd')
            cpu_nice = os.path.join(self.base_path, f'{type}-nice.rrd')
            cpu_user = os.path.join(self.base_path, f'{type}-user.rrd')
            cpu_system = os.path.join(self.base_path, f'{type}-system.rrd')
            cpu_interrupt = os.path.join(self.base_path, f'{type}-interrupt.rrd')
        else:
            cpu_idle = os.path.join(self.base_path, 'cpu-idle.rrd')
            cpu_nice = os.path.join(self.base_path, 'cpu-nice.rrd')
            cpu_user = os.path.join(self.base_path, 'cpu-user.rrd')
            cpu_system = os.path.join(self.base_path, 'cpu-system.rrd')
            cpu_interrupt = os.path.join(self.base_path, 'cpu-interrupt.rrd')

        return [cpu_idle, cpu_nice, cpu_user, cpu_system, cpu_interrupt]

    def get_defs(self, identifier):
        if self.middleware.call_sync('reporting.config')['cpu_in_percentage']:
            type = 'gauge'
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


class CPUTempPlugin(RRDBase):

    title = 'CPU Temperature'
    vertical_label = '\u00b0C'

    def get_rrd_files(self, identifier):
        files = []
        for n in itertools.count():
            file = os.path.join(self._base_path, f'cputemp-{n}', 'temperature.rrd')
            if os.path.exists(file):
                files.append(file)
            else:
                break

        return files

    def get_identifiers(self):
        if not self.get_defs(None):
            return []

        return None

    def get_defs(self, identifier):
        args = []
        for n, cputemp_file in enumerate(self.get_rrd_files(identifier)):
            a = [
                f'DEF:s_avg{n}={cputemp_file}:value:AVERAGE',
                f'CDEF:avg{n}=s_avg{n},10,/,273.2,-',
                f'XPORT:avg{n}:cputemp{n}'
            ]
            args.extend(a)

        return args


class DiskTempPlugin(RRDBase):

    vertical_label = '\u00b0C'
    rrd_types = (
        RRDType('temperature', 'value'),
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
        RRDType('if_octets', 'rx', '%name%,8,*', 'rx'),
        RRDType('if_octets', 'tx', '%name%,8,*', 'tx'),
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
    rrd_types = (
        RRDType('memory-used', 'value'),
        RRDType('memory-free', 'value'),
        RRDType('memory-cached', 'value'),
        RRDType('memory-buffered', 'value'),
    )


class LoadPlugin(RRDBase):

    title = 'System Load'
    vertical_label = 'Processes'
    rrd_types = (
        RRDType('load', 'shortterm'),
        RRDType('load', 'midterm'),
        RRDType('load', 'longterm'),
    )


class NFSStatPlugin(RRDBase):

    plugin = 'nfsstat-server'
    title = 'NFS Stats (Operations)'
    vertical_label = 'Operations/s'
    rrd_types = (
        RRDType('nfsstat-read', 'value'),
        RRDType('nfsstat-write', 'value'),
    )


class NFSStatBytesPlugin(RRDBase):

    plugin = 'nfsstat-server'
    title = 'NFS Stats (Bytes)'
    vertical_label = 'Bytes/s'
    rrd_types = (
        RRDType('nfsstat-read_bytes', 'value'),
        RRDType('nfsstat-write_bytes', 'value'),
    )


class ProcessesPlugin(RRDBase):

    title = 'Processes'
    vertical_label = 'Processes'
    rrd_types = (
        RRDType('ps_state-sleeping', 'value'),
        RRDType('ps_state-running', 'value'),
        RRDType('ps_state-stopped', 'value'),
        RRDType('ps_state-zombies', 'value'),
        RRDType('ps_state-blocked', 'value'),
    )
    stacked = True


class SwapPlugin(RRDBase):

    title = 'Swap Utilization'
    vertical_label = 'Bytes'
    rrd_types = (
        RRDType('swap-used', 'value'),
        RRDType('swap-free', 'value'),
    )
    stacked = True


class DFPlugin(RRDBase):

    vertical_label = 'Bytes'
    rrd_types = (
        RRDType('df_complex-free', 'value'),
        RRDType('df_complex-used', 'value'),
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
        RRDType('uptime', 'value', '%name%,86400,/'),
    )


class DiskPlugin(RRDBase):

    vertical_label = 'Bytes/s'
    rrd_types = (
        RRDType('disk_octets', 'read'),
        RRDType('disk_octets', 'write'),
    )

    RE_NVME_N = re.compile(r"(nvme[0-9]+)(n[0-9]+)$")

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

    def encode(self, identifier):
        if m := self.RE_NVME_N.match(identifier):
            nvme_namespace = f'{m.group(1)}c0{m.group(2)}'
            # If NVMe namespace exists then stats are reported there
            if os.path.exists(f'{self._base_path}/disk-{nvme_namespace}/disk_octets.rrd'):
                if os.path.exists(f'/dev/{nvme_namespace}'):
                    return nvme_namespace

        return identifier


class ARCSizePlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = 'Bytes'
    rrd_types = (
        RRDType('cache_size-arc', 'value'),
        RRDType('cache_size-L2', 'value'),
    )

    def get_title(self):
        return 'ARC Size'


class ARCRatioPlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = 'Hits (%)'
    rrd_types = (
        RRDType('cache_ratio-arc', 'value', '%name%,100,*'),
        RRDType('cache_ratio-L2', 'value', '%name%,100,*'),
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
            RRDType(f'cache_result-{identifier}-hit', 'value', '%name%,100,*'),
            RRDType(f'cache_result-{identifier}-miss', 'value', '%name%,100,*'),
        )

    def get_title(self):
        return 'ARC Requests ({identifier})'

    def get_identifiers(self):
        return ['demand_data', 'demand_metadata', 'prefetch_data', 'prefetch_metadata']
