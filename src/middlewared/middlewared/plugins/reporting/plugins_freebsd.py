import glob
import os
import re
import sysctl

from .rrd_utils import RRDBase


RE_DISK = re.compile(r'^[a-z]+[0-9]+$')


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
                f'CDEF:avg{n}=s_avg{n},10,/,273.15,-',
                f'XPORT:avg{n}:cputemp{n}'
            ]
            args.extend(a)
        return args


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


class GeomStatBase(object):

    geom_stat_name = None

    def get_identifiers(self):
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


class NFSStatPlugin(RRDBase):

    plugin = 'nfsstat-server'
    title = 'NFS Stats (Operations)'
    vertical_label = 'Operations/s'
    rrd_types = (
        ('nfsstat-read', 'value', None),
        ('nfsstat-write', 'value', None),
    )


class NFSStatBytesPlugin(RRDBase):

    plugin = 'nfsstat-server'
    title = 'NFS Stats (Bytes)'
    vertical_label = 'Bytes/s'
    rrd_types = (
        ('nfsstat-read_bytes', 'value', None),
        ('nfsstat-write_bytes', 'value', None),
    )


class UPSBase(object):

    plugin = 'nut'

    def get_identifiers(self):
        ups_identifier = self.middleware.call_sync('ups.config')['identifier']

        if all(os.path.exists(os.path.join(self._base_path, f'{self.plugin}-{ups_identifier}', f'{_type}.rrd'))
               for _type, dsname, transform, in self.rrd_types):
            return [ups_identifier]

        return []


class UPSBatteryChargePlugin(UPSBase, RRDBase):

    title = 'UPS Battery Statistics'
    vertical_label = 'Percent'
    rrd_types = (
        ('percent-charge', 'value', None),
    )


class UPSRemainingBatteryPlugin(UPSBase, RRDBase):

    title = 'UPS Battery Time Remaining Statistics'
    vertical_label = 'Minutes'
    rrd_types = (
        ('timeleft-battery', 'value', '%name%,60,/'),
    )
