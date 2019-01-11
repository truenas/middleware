import errno
import glob
import json
import os
import re
import subprocess
import sysctl
import textwrap

from middlewared.schema import Dict, Int, Str, accepts
from middlewared.service import CallError, Service, filterable
from middlewared.utils import filter_list

RE_COLON = re.compile('(.+):(.+)$')
RE_DISK = re.compile(r'^[a-z]+[0-9]+$')
RE_NAME = re.compile(r'(%name_(\d+)%)')
RE_NAME_NUMBER = re.compile(r'(.+?)(\d+)$')
RE_RRDPLUGIN = re.compile(r'^(?P<name>.+)Plugin$')
RE_SPACES = re.compile(r'\s{2,}')
RRD_BASE_PATH = '/var/db/collectd/rrd/localhost'
RRD_PLUGINS = {}


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = RE_RRDPLUGIN.search(name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group('name').lower()
        elif name != 'RRDBase' and not hasattr(klass, 'plugin'):
            raise ValueError(f'Could not determine plugin name for {name!r}')

        if reg and not hasattr(klass, 'name'):
            klass.name = reg.group('name').lower()
            RRD_PLUGINS[klass.name] = klass
        elif hasattr(klass, 'name'):
            RRD_PLUGINS[klass.name] = klass
        elif name != 'RRDBase':
            raise ValueError(f'Could not determine class name for {name!r}')
        return klass


class RRDBase(object, metaclass=RRDMeta):

    base_path = None
    title = None
    vertical_label = None
    identifier_plugin = True
    rrd_types = None
    rrd_data_extra = None

    def __init__(self, middleware):
        self.middleware = middleware
        self._base_path = RRD_BASE_PATH
        self.base_path = os.path.join(self._base_path, self.plugin)

    def __repr__(self):
        return f'<RRD:{self.plugin}>'

    def get_title(self):
        return self.title

    def get_vertical_label(self):
        return self.vertical_label

    def get_rrd_types(self, identifier=None):
        return self.rrd_types

    def __getstate__(self):
        return {
            'name': self.name,
            'title': self.get_title(),
            'vertical_label': self.get_vertical_label(),
            'identifiers': self.get_identifiers(),
        }

    @staticmethod
    def _sort_ports(entry):
        if entry == 'ha':
            pref = '0'
            body = entry
        else:
            reg = RE_COLON.search(entry)
            if reg:
                pref = reg.group(1)
                body = reg.group(2)
            else:
                pref = ''
                body = entry
        reg = RE_NAME_NUMBER.search(body)
        if not reg:
            return (pref, body, -1)
        return (pref, reg.group(1), int(reg.group(2)))

    @staticmethod
    def _sort_disks(entry):
        reg = RE_NAME_NUMBER.search(entry)
        if not reg:
            return (entry, )
        if reg:
            return (reg.group(1), int(reg.group(2)))

    def get_identifiers(self):
        return None

    def encode(self, identifier):
        return identifier

    def get_defs(self, identifier):

        rrd_types = self.get_rrd_types(identifier)
        if not rrd_types:
            raise RuntimeError(f'rrd_types not defined for {self.name!r}')

        args = []
        defs = {}
        for i, rrd_type in enumerate(rrd_types):
            _type, dsname, transform = rrd_type
            direc = self.plugin
            if self.identifier_plugin and identifier:
                identifier = self.encode(identifier)
                direc += f'-{identifier}'
            path = os.path.join(self._base_path, direc, f'{_type}.rrd')
            path = path.replace(':', r'\:')
            name = f'{_type}_{dsname}'
            defs[i] = {
                'name': name,
                'transform': transform,
            }
            args += [
                f'DEF:{name}={path}:{dsname}:AVERAGE',
            ]

        for i, attrs in defs.items():
            if attrs['transform']:
                transform = attrs['transform']
                if '%name%' in transform:
                    transform = transform.replace('%name%', attrs['name'])
                for orig, number in RE_NAME.findall(transform):
                    transform = transform.replace(orig, defs[int(number)]['name'])
                args += [
                    f'CDEF:c{attrs["name"]}={transform}',
                    f'XPORT:c{attrs["name"]}:{attrs["name"]}',
                ]
            else:
                args += [f'XPORT:{attrs["name"]}:{attrs["name"]}']

        if self.rrd_data_extra:
            extra = textwrap.dedent(self.rrd_data_extra)
            for orig, number in RE_NAME.findall(extra):
                def_ = defs[int(number)]
                name = def_['name']
                if def_['transform']:
                    name = 'c' + name
                extra = extra.replace(orig, name)
            args += extra.split()

        return args

    def export(self, identifier, unit, page):
        unit = unit[0].lower()
        starttime = f'1{unit}'
        if not page:
            endtime = 'now'
        else:
            endtime = f'now-{page}{unit}'

        args = [
            'rrdtool',
            'xport',
            '--daemon', 'unix:/var/run/rrdcached.sock',
            '--json',
            '--end', endtime,
            '--start', f'end-{starttime}',
        ]
        args.extend(self.get_defs(identifier))
        cp = subprocess.run(args, capture_output=True)
        if cp.returncode != 0:
            raise RuntimeError(f'Failed to export RRD data: {cp.stderr.decode()}')

        data = json.loads(cp.stdout)
        data = dict(
            data=data['data'],
            **data['meta'],
        )

        return data


class CPUPlugin(RRDBase):

    plugin = 'aggregation-cpu-sum'
    title = 'CPU Usage'
    vertical_label = '%CPU'

    def get_defs(self, identifier):
        if self.middleware.call_sync('system.advanced.config')['cpu_in_percentage']:
            cpu_idle = os.path.join(self.base_path, 'percent-idle.rrd')
            cpu_nice = os.path.join(self.base_path, 'percent-nice.rrd')
            cpu_user = os.path.join(self.base_path, 'percent-user.rrd')
            cpu_system = os.path.join(self.base_path, 'percent-system.rrd')
            cpu_interrupt = os.path.join(self.base_path, 'percent-interrupt.rrd')

            args = [
                f'DEF:idle={cpu_idle}:value:AVERAGE',
                f'DEF:nice={cpu_nice}:value:AVERAGE',
                f'DEF:user={cpu_user}:value:AVERAGE',
                f'DEF:system={cpu_system}:value:AVERAGE',
                f'DEF:interrupt={cpu_interrupt}:value:AVERAGE',
                'CDEF:cinterrupt=interrupt,UN,0,interrupt,IF',
                'CDEF:csystem=system,UN,0,system,IF,cinterrupt,+',
                'CDEF:cuser=user,UN,0,user,IF,csystem,+',
                'CDEF:cnice=nice,UN,0,nice,IF,cuser,+',
                'CDEF:cidle=idle,UN,0,idle,IF,cnice,+',
                'XPORT:cinterrupt:interrupt',
                'XPORT:csystem:system',
                'XPORT:cuser:user',
                'XPORT:cnice:nice',
                'XPORT:cidle:idle',
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
                'CDEF:cinterrupt=interrupt_p,UN,0,interrupt_p,IF',
                'CDEF:csystem=system_p,UN,0,system_p,IF,cinterrupt,+',
                'CDEF:cuser=user_p,UN,0,user_p,IF,csystem,+',
                'CDEF:cnice=nice_p,UN,0,nice_p,IF,cuser,+',
                'CDEF:cidle=idle_p,UN,0,idle_p,IF,cnice,+',
                'XPORT:cinterrupt:interrupt',
                'XPORT:csystem:system',
                'XPORT:cuser:user',
                'XPORT:cnice:nice',
                'XPORT:cidle:idle',
            ]

            return args


class CPUTempPlugin(RRDBase):

    title = 'CPU Temperature'
    vertical_label = '\u00b0C'

    def __get_cputemp_file__(self, n):
        cputemp_file = os.path.join(self._base_path, f'cputemp-{n}', 'temperature.rrd')
        if os.path.isfile(cputemp_file):
            return cputemp_file

    def __get_number_of_cores__(self):
        try:
            return sysctl.filter('kern.smp.cpus')[0].value
        except Exception:
            return 0

    def __check_cputemp_avail__(self):
        n_cores = self.__get_number_of_cores__()
        if n_cores > 0:
            for n in range(0, n_cores):
                if self.__get_cputemp_file__(n) is None:
                    return False
        else:
            return False
        return True

    def get_identifiers(self):
        if not self.__check_cputemp_avail__():
            return []
        return None

    def get_defs(self, identifier):
        args = []
        for n in range(0, self.__get_number_of_cores__()):
            cputemp_file = self.__get_cputemp_file__(n)
            a = [
                f'DEF:s_avg{n}={cputemp_file}:value:AVERAGE',
                f'CDEF:avg{n}=s_avg{0},10,/,273.15,-',
                f'XPORT:avg{n}:cputemp{n}'
            ]
            args.extend(a)
        return args


class DiskTempPlugin(RRDBase):

    vertical_label = '\u00b0C'
    rrd_types = (
        ('temperature', 'value', None),
    )

    def get_title(self):
        return 'Disk Temperature {identifier}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob(f'{self._base_path}/disktemp-*'):
            ident = entry.rsplit('-', 1)[-1]
            if os.path.exists(os.path.join(entry, 'temperature.rrd')):
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
    rrd_types = (
        ('memory-wired', 'value', '%name%,UN,0,%name%,IF'),
        ('memory-inactive', 'value', '%name%,UN,0,%name%,IF,%name_0%,+'),
        ('memory-laundry', 'value', '%name%,UN,0,%name%,IF,%name_1%,+'),
        ('memory-active', 'value', '%name%,UN,0,%name%,IF,%name_2%,+'),
        ('memory-free', 'value', '%name%,UN,0,%name%,IF,%name_3%,+'),
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
    rrd_types = (
        ('ps_state-wait', 'value', '%name%,UN,0,%name%,IF'),
        ('ps_state-idle', 'value', '%name%,UN,0,%name%,IF,%name_0%,+'),
        ('ps_state-sleeping', 'value', '%name%,UN,0,%name%,IF,%name_1%,+'),
        ('ps_state-running', 'value', '%name%,UN,0,%name%,IF,%name_2%,+'),
        ('ps_state-stopped', 'value', '%name%,UN,0,%name%,IF,%name_3%,+'),
        ('ps_state-zombies', 'value', '%name%,UN,0,%name%,IF,%name_4%,+'),
        ('ps_state-blocked', 'value', '%name%,UN,0,%name%,IF,%name_5%,+'),
    )


class SwapPlugin(RRDBase):

    title = 'Swap Utilization'
    vertical_label = 'Bytes'
    rrd_types = (
        ('swap-used', 'value', '%name%,UN,0,%name%,IF'),
        ('swap-free', 'value', '%name%,UN,0,%name%,IF,%name_0%,+'),
    )


class DFPlugin(RRDBase):

    vertical_label = 'Bytes'
    rrd_types = (
        ('df_complex-free', 'value', None),
        ('df_complex-used', 'value', None),
    )
    rrd_data_extra = """
        CDEF:both=%name_0%,%name_1%,+
        XPORT:both:both
    """

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
            entry = RE_SPACES.split(line)[-1]
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


class CTLPlugin(RRDBase):

    vertical_label = 'Bytes/s'
    rrd_types = (
        ('disk_octets', 'read', None),
        ('disk_octets', 'write', None),
    )

    def get_title(self):
        return 'SCSI target port ({identifier})'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob(f'{self._base_path}/ctl-*'):
            ident = entry.split('-', 1)[-1]
            if ident.endswith('ioctl'):
                continue
            if os.path.exists(os.path.join(entry, 'disk_octets.rrd')):
                ids.append(ident)

        ids.sort(key=RRDBase._sort_ports)
        return ids


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


class GeomStatBase(object):

    geom_stat_name = None

    def get_identifiers(self):
        print("hm")
        ids = []
        for entry in glob.glob(f'{self._base_path}/geom_stat/{self.geom_stat_name}-*'):
            ident = entry.split('-', 1)[-1].replace('.rrd', '')
            if not RE_DISK.match(ident):
                continue
            if not os.path.exists(f'/dev/{ident}'):
                continue
            if ident.startswith('pass'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids


class DiskGeomBusyPlugin(GeomStatBase, RRDBase):

    geom_stat_name = 'geom_busy_percent'
    identifier_plugin = False
    plugin = 'geom_stat'
    vertical_label = 'Percent'

    def get_rrd_types(self, identifier):
        return (
            (f'geom_busy_percent-{identifier}', 'value', None),
        )

    def get_title(self):
        return 'Disk Busy ({identifier})'


class DiskGeomLatencyPlugin(GeomStatBase, RRDBase):

    geom_stat_name = 'geom_latency'
    identifier_plugin = False
    plugin = 'geom_stat'
    vertical_label = 'Time,msec'

    def get_rrd_types(self, identifier):
        return (
            (f'geom_latency-{identifier}', 'read', None),
            (f'geom_latency-{identifier}', 'write', None),
            (f'geom_latency-{identifier}', 'delete', None),
        )

    def get_title(self):
        return 'Disk Latency ({identifier})'


class DiskGeomOpsRWDPlugin(GeomStatBase, RRDBase):

    geom_stat_name = 'geom_ops_rwd'
    identifier_plugin = False
    plugin = 'geom_stat'
    vertical_label = 'Operations/s'

    def get_rrd_types(self, identifier):
        return (
            (f'geom_ops_rwd-{identifier}', 'read', None),
            (f'geom_ops_rwd-{identifier}', 'write', None),
            (f'geom_ops_rwd-{identifier}', 'delete', None),
        )

    def get_title(self):
        return 'Disk Operations detailed ({identifier})'


class DiskGeomQueuePlugin(GeomStatBase, RRDBase):

    geom_stat_name = 'geom_queue'
    identifier_plugin = False
    plugin = 'geom_stat'
    vertical_label = 'Requests'

    def get_rrd_types(self, identifier):
        return (
            (f'geom_queue-{identifier}', 'length', None),
        )

    def get_title(self):
        return 'Pending I/O requests on ({identifier})'


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
    rrd_data_extra = """
        CDEF:total=%name_0%,%name_1%,+
        XPORT:total:total
    """

    def get_rrd_types(self, identifier):
        return (
            (f'cache_result-{identifier}-hit', 'value', '%name%,100,*'),
            (f'cache_result-{identifier}-miss', 'value', '%name%,100,*'),
        )

    def get_title(self):
        return 'ARC Requests ({identifier})'

    def get_identifiers(self):
        return ('demand_data', 'demand_metadata', 'prefetch_data', 'prefetch_metadata')


class NFSStatPlugin(RRDBase):

    title = 'NFS Stats'
    vertical_label = 'Bytes'
    rrd_types = (
        ('nfsstat-read', 'value', None),
        ('nfsstat-write', 'value', None),
    )


class ReportingService(Service):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__rrds = {}
        for name, klass in RRD_PLUGINS.items():
            self.__rrds[name] = klass(self.middleware)

    @filterable
    def graphs(self, filters, options):
        return filter_list([i.__getstate__() for i in self.__rrds.values()], filters, options)

    @accepts(
        Str('name'),
        Str('identifier', null=True),
        Dict(
            'query',
            Str('unit', enum=[
                'HOURLY', 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
            ], default='HOURLY'),
            Int('page', default=0),
        )
    )
    def get_data(self, name, ident, query):
        try:
            rrd = self.__rrds[name]
        except KeyError:
            raise CallError(f'Graph {name!r} not found.', errno.ENOENT)
        return rrd.export(ident, query['unit'], query['page'])
