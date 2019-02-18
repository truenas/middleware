# Copyright 2012 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import glob
import logging
import os
import re
import tempfile
import subprocess

from freenasUI.common.pipesubr import pipeopen
from freenasUI.middleware.client import client
from freenasUI.system.models import Reporting
from middlewared.utils import cache_with_autorefresh, filter_list


log = logging.getLogger('reporting.rrd')

name2plugin = dict()


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = re.search(r'^(?P<name>.+)Plugin$', name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group("name").lower()
        elif name != 'RRDBase' and not hasattr(klass, 'plugin'):
            raise ValueError("Could not determine plugin name %s" % str(name))

        if reg and not hasattr(klass, 'name'):
            klass.name = reg.group("name").lower()
            name2plugin[klass.name] = klass
        elif hasattr(klass, 'name'):
            name2plugin[klass.name] = klass
        elif name != 'RRDBase':
            raise ValueError("Could not determine plugin name %s" % str(name))
        return klass


class RRDBase(object, metaclass=RRDMeta):

    base_path = None
    identifier = None
    title = None
    vertical_label = None
    imgformat = 'PNG'
    unit = 'hourly'
    step = 0

    def __init__(self, base_path, identifier=None, unit=None, step=None):
        if identifier is not None:
            self.identifier = str(identifier)
        if unit is not None:
            self.unit = str(unit)
        if step is not None:
            self.step = int(step)
        self._base_path = base_path
        self.base_path = os.path.join(base_path, self.plugin)

    def __repr__(self):
        return '<RRD:%s>' % self.plugin

    def graph(self):
        raise NotImplementedError

    def get_title(self):
        return self.title

    def get_vertical_label(self):
        return self.vertical_label

    @staticmethod
    def _sort_ports(entry):
        if entry == "ha":
            pref = "0"
            body = entry
        else:
            reg = re.search('(.+):(.+)$', entry)
            if reg:
                pref = reg.group(1)
                body = reg.group(2)
            else:
                pref = ""
                body = entry
        reg = re.search('(.+?)(\d+)$', body)
        if not reg:
            return (pref, body, -1)
        return (pref, reg.group(1), int(reg.group(2)))

    @staticmethod
    def _sort_disks(entry):
        reg = re.search('(.+?)(\d+)$', entry)
        if not reg:
            return (entry, )
        if reg:
            return (reg.group(1), int(reg.group(2)))

    def get_identifiers(self):
        return None

    def generate(self):
        """
        Call rrdgraph to generate the graph on a temp file

        Returns:
            str - path to the image
        """

        starttime = '1%s' % (self.unit[0], )
        if self.step == 0:
            endtime = 'now'
        else:
            endtime = 'now-%d%s' % (self.step, self.unit[0], )

        fh, path = tempfile.mkstemp()
        args = [
            "/usr/local/bin/rrdtool",
            "graph",
            path,
            '--daemon', 'unix:/var/run/rrdcached.sock',
            '--imgformat', self.imgformat,
            '--vertical-label', str(self.get_vertical_label()),
            '--title', str(self.get_title()),
            '--lower-limit', '0',
            '--end', endtime,
            '--start', 'end-%s' % starttime, '-b', '1024',
        ]
        args.extend(self.graph())
        # rrdtool python is suffering from some sort of threading locking issue
        # See #3478
        # rrdtool.graph(*args)
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        err = proc.communicate()[1]
        if proc.returncode != 0:
            log.error("Failed to generate graph: %s", err)
        return fh, path


class CPUPlugin(RRDBase):

    plugin = "aggregation-cpu-sum"
    title = "CPU Usage"
    vertical_label = "%CPU"

    def graph(self):
        if Reporting.objects.latest('id').cpu_in_percentage:
            cpu_idle = os.path.join(self.base_path, "percent-idle.rrd")
            cpu_nice = os.path.join(self.base_path, "percent-nice.rrd")
            cpu_user = os.path.join(self.base_path, "percent-user.rrd")
            cpu_system = os.path.join(self.base_path, "percent-system.rrd")
            cpu_interrupt = os.path.join(self.base_path, "percent-interrupt.rrd")

            args = [
                'DEF:min0=%s:value:MIN' % cpu_idle,
                'DEF:avg0=%s:value:AVERAGE' % cpu_idle,
                'DEF:max0=%s:value:MAX' % cpu_idle,
                'DEF:min1=%s:value:MIN' % cpu_nice,
                'DEF:avg1=%s:value:AVERAGE' % cpu_nice,
                'DEF:max1=%s:value:MAX' % cpu_nice,
                'DEF:min2=%s:value:MIN' % cpu_user,
                'DEF:avg2=%s:value:AVERAGE' % cpu_user,
                'DEF:max2=%s:value:MAX' % cpu_user,
                'DEF:min3=%s:value:MIN' % cpu_system,
                'DEF:avg3=%s:value:AVERAGE' % cpu_system,
                'DEF:max3=%s:value:MAX' % cpu_system,
                'DEF:min4=%s:value:MIN' % cpu_interrupt,
                'DEF:avg4=%s:value:AVERAGE' % cpu_interrupt,
                'DEF:max4=%s:value:MAX' % cpu_interrupt,
                'CDEF:cdef4=avg4,UN,0,avg4,IF',
                'CDEF:cdef3=avg3,UN,0,avg3,IF,cdef4,+',
                'CDEF:cdef2=avg2,UN,0,avg2,IF,cdef3,+',
                'CDEF:cdef1=avg1,UN,0,avg1,IF,cdef2,+',
                'CDEF:cdef0=avg0,UN,0,avg0,IF,cdef1,+',
                'AREA:cdef0#f9f9f9',
                'AREA:cdef1#bff7bf',
                'AREA:cdef2#bfbfff',
                'AREA:cdef3#ffbfbf',
                'AREA:cdef4#e7bfe7',
                'LINE1:cdef0#e8e8e8:Idle  ',
                'GPRINT:min0:MIN:%5.2lf%% Min,',
                'GPRINT:avg0:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max0:MAX:%5.2lf%% Max,',
                'GPRINT:avg0:LAST:%5.2lf%% Last\l',
                'LINE1:cdef1#00e000:Nice  ',
                'GPRINT:min1:MIN:%5.2lf%% Min,',
                'GPRINT:avg1:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max1:MAX:%5.2lf%% Max,',
                'GPRINT:avg1:LAST:%5.2lf%% Last\l',
                'LINE1:cdef2#0000ff:User  ',
                'GPRINT:min2:MIN:%5.2lf%% Min,',
                'GPRINT:avg2:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max2:MAX:%5.2lf%% Max,',
                'GPRINT:avg2:LAST:%5.2lf%% Last\l',
                'LINE1:cdef3#ff0000:System',
                'GPRINT:min3:MIN:%5.2lf%% Min,',
                'GPRINT:avg3:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max3:MAX:%5.2lf%% Max,',
                'GPRINT:avg3:LAST:%5.2lf%% Last\l',
                'LINE1:cdef4#a000a0:IRQ   ',
                'GPRINT:min4:MIN:%5.2lf%% Min,',
                'GPRINT:avg4:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max4:MAX:%5.2lf%% Max,',
                'GPRINT:avg4:LAST:%5.2lf%% Last\l',
            ]

            return args

        else:
            cpu_idle = os.path.join(self.base_path, "cpu-idle.rrd")
            cpu_nice = os.path.join(self.base_path, "cpu-nice.rrd")
            cpu_user = os.path.join(self.base_path, "cpu-user.rrd")
            cpu_system = os.path.join(self.base_path, "cpu-system.rrd")
            cpu_interrupt = os.path.join(self.base_path, "cpu-interrupt.rrd")

            args = [
                'DEF:min0_raw=%s:value:MIN' % cpu_idle,
                'DEF:avg0_raw=%s:value:AVERAGE' % cpu_idle,
                'DEF:max0_raw=%s:value:MAX' % cpu_idle,
                'DEF:min1_raw=%s:value:MIN' % cpu_nice,
                'DEF:avg1_raw=%s:value:AVERAGE' % cpu_nice,
                'DEF:max1_raw=%s:value:MAX' % cpu_nice,
                'DEF:min2_raw=%s:value:MIN' % cpu_user,
                'DEF:avg2_raw=%s:value:AVERAGE' % cpu_user,
                'DEF:max2_raw=%s:value:MAX' % cpu_user,
                'DEF:min3_raw=%s:value:MIN' % cpu_system,
                'DEF:avg3_raw=%s:value:AVERAGE' % cpu_system,
                'DEF:max3_raw=%s:value:MAX' % cpu_system,
                'DEF:min4_raw=%s:value:MIN' % cpu_interrupt,
                'DEF:avg4_raw=%s:value:AVERAGE' % cpu_interrupt,
                'DEF:max4_raw=%s:value:MAX' % cpu_interrupt,
                'CDEF:min_total=min0_raw,min1_raw,min2_raw,min3_raw,min4_raw,+,+,+,+',
                'CDEF:avg_total=avg0_raw,avg1_raw,avg2_raw,avg3_raw,avg4_raw,+,+,+,+',
                'CDEF:max_total=max0_raw,max1_raw,max2_raw,max3_raw,max4_raw,+,+,+,+',
                'CDEF:min0=min0_raw,min_total,/,100,*',
                'CDEF:avg0=avg0_raw,avg_total,/,100,*',
                'CDEF:max0=max0_raw,max_total,/,100,*',
                'CDEF:min1=min1_raw,min_total,/,100,*',
                'CDEF:avg1=avg1_raw,avg_total,/,100,*',
                'CDEF:max1=max1_raw,max_total,/,100,*',
                'CDEF:min2=min2_raw,min_total,/,100,*',
                'CDEF:avg2=avg2_raw,avg_total,/,100,*',
                'CDEF:max2=max2_raw,max_total,/,100,*',
                'CDEF:min3=min3_raw,min_total,/,100,*',
                'CDEF:avg3=avg3_raw,avg_total,/,100,*',
                'CDEF:max3=max3_raw,max_total,/,100,*',
                'CDEF:min4=min4_raw,min_total,/,100,*',
                'CDEF:avg4=avg4_raw,avg_total,/,100,*',
                'CDEF:max4=max4_raw,max_total,/,100,*',
                'CDEF:cdef4=avg4,UN,0,avg4,IF',
                'CDEF:cdef3=avg3,UN,0,avg3,IF,cdef4,+',
                'CDEF:cdef2=avg2,UN,0,avg2,IF,cdef3,+',
                'CDEF:cdef1=avg1,UN,0,avg1,IF,cdef2,+',
                'CDEF:cdef0=avg0,UN,0,avg0,IF,cdef1,+',
                'AREA:cdef0#f9f9f9',
                'AREA:cdef1#bff7bf',
                'AREA:cdef2#bfbfff',
                'AREA:cdef3#ffbfbf',
                'AREA:cdef4#e7bfe7',
                'LINE1:cdef0#e8e8e8:Idle  ',
                'GPRINT:min0:MIN:%5.2lf%% Min,',
                'GPRINT:avg0:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max0:MAX:%5.2lf%% Max,',
                'GPRINT:avg0:LAST:%5.2lf%% Last\l',
                'LINE1:cdef1#00e000:Nice  ',
                'GPRINT:min1:MIN:%5.2lf%% Min,',
                'GPRINT:avg1:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max1:MAX:%5.2lf%% Max,',
                'GPRINT:avg1:LAST:%5.2lf%% Last\l',
                'LINE1:cdef2#0000ff:User  ',
                'GPRINT:min2:MIN:%5.2lf%% Min,',
                'GPRINT:avg2:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max2:MAX:%5.2lf%% Max,',
                'GPRINT:avg2:LAST:%5.2lf%% Last\l',
                'LINE1:cdef3#ff0000:System',
                'GPRINT:min3:MIN:%5.2lf%% Min,',
                'GPRINT:avg3:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max3:MAX:%5.2lf%% Max,',
                'GPRINT:avg3:LAST:%5.2lf%% Last\l',
                'LINE1:cdef4#a000a0:IRQ   ',
                'GPRINT:min4:MIN:%5.2lf%% Min,',
                'GPRINT:avg4:AVERAGE:%5.2lf%% Avg,',
                'GPRINT:max4:MAX:%5.2lf%% Max,',
                'GPRINT:avg4:LAST:%5.2lf%% Last\l',
            ]

            return args


class CPUTempPlugin(RRDBase):

    title = "CPU Temperature"
    vertical_label = "\u00b0C"

    def __get_cputemp_file__(self, n):
        cputemp_file = os.path.join(
            "%s/cputemp-%s" % (self._base_path, n),
            "temperature.rrd")
        if os.path.isfile(cputemp_file):
            return cputemp_file
        else:
            return None

    def __get_number_of_cores__(self):
        proc = pipeopen('/sbin/sysctl -n kern.smp.cpus', important=False, logger=log)
        proc_out = proc.communicate()[0]
        try:
            return int(proc_out)
        except:
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

    def graph(self):
        args = []
        colors = [
            '#00ff00', '#0000ff', '#ff0000', '#ff00ff',
            '#ffff00', '#00ffff', '#800000', '#008000',
            '#000080', '#008080', '#808000', '#800080',
            '#808080', '#C0C0C0', '#654321', '#123456'
        ]
        for n in range(0, self.__get_number_of_cores__()):
            cputemp_file = self.__get_cputemp_file__(n)
            a = [
                'DEF:s_min{0}={1}:value:MIN'.format(n, cputemp_file),
                'DEF:s_avg{0}={1}:value:AVERAGE'.format(n, cputemp_file),
                'DEF:s_max{0}={1}:value:MAX'.format(n, cputemp_file),
                'CDEF:min{0}=s_min{0},10,/,273.15,-'.format(n),
                'CDEF:avg{0}=s_avg{0},10,/,273.15,-'.format(n),
                'CDEF:max{0}=s_max{0},10,/,273.15,-'.format(n),
                'AREA:max{0}#bfffbf'.format(n),
                'AREA:min{0}#FFFFFF'.format(n),
                'LINE1:avg{0}{1}: Core {2}'.format(n, colors[n % len(colors)], n + 1),
                'GPRINT:min{0}:MIN:%.1lf\u00b0 Min,'.format(n),
                'GPRINT:avg{0}:AVERAGE:%.1lf\u00b0 Avg,'.format(n),
                'GPRINT:max{0}:MAX:%.1lf\u00b0 Max,'.format(n),
                'GPRINT:avg{0}:LAST:%.1lf\u00b0 Last\l'.format(n)
            ]
            args.extend(a)
        return args


class DiskTempPlugin(RRDBase):

    vertical_label = "\u00b0C"

    def get_title(self):
        return f'Disk Temperature ({self.identifier})'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/disktemp-*' % self._base_path):
            ident = entry.rsplit('-', 1)[-1]
            if os.path.exists(os.path.join(entry, 'temperature.rrd')):
                ids.append(ident)
        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):
        path = os.path.join(
            "%s/disktemp-%s" % (self._base_path, self.identifier),
            "temperature.rrd"
        )

        args = [
            'DEF:temp_raw=%s:value:AVERAGE' % path,
            'CDEF:temp=temp_raw',
            'AREA:temp#bfbfff',
            'LINE1:temp#0000ff:Temperature',
            'GPRINT:temp:AVERAGE:%.1lf\u00b0 Avg',
        ]

        return args


class InterfacePlugin(RRDBase):

    vertical_label = "Bits/s"

    def get_title(self):
        return 'Interface Traffic (%s)' % self.identifier

    def get_identifiers(self):
        ids = []
        proc = pipeopen("/sbin/ifconfig -l", important=False, logger=log)
        ifaces = proc.communicate()[0].strip('\n').split(' ')
        for entry in glob.glob('%s/interface-*' % self._base_path):
            ident = entry.rsplit('-', 1)[-1]
            if ident not in ifaces:
                continue
            if re.match(r'(usbus|ipfw|pfsync|pflog|carp)', ident):
                continue
            if os.path.exists(os.path.join(entry, 'if_octets.rrd')):
                ids.append(ident)
        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):
        path = os.path.join(
            "%s/interface-%s" % (self._base_path, self.identifier),
            "if_octets.rrd"
        )
        # Escape interfaces with colon in the name
        # See #28470
        path = path.replace(':', '\\:')

        args = [
            'DEF:min_rx_raw=%s:rx:MIN' % path,
            'DEF:avg_rx_raw=%s:rx:AVERAGE' % path,
            'DEF:max_rx_raw=%s:rx:MAX' % path,
            'DEF:min_tx_raw=%s:tx:MIN' % path,
            'DEF:avg_tx_raw=%s:tx:AVERAGE' % path,
            'DEF:max_tx_raw=%s:tx:MAX' % path,
            'CDEF:min_rx=min_rx_raw,8,*',
            'CDEF:avg_rx=avg_rx_raw,8,*',
            'CDEF:max_rx=max_rx_raw,8,*',
            'CDEF:min_tx=min_tx_raw,8,*',
            'CDEF:avg_tx=avg_tx_raw,8,*',
            'CDEF:max_tx=max_tx_raw,8,*',
            'CDEF:avg_rx_bytes=avg_rx,8,/',
            'VDEF:global_min_rx=min_rx,MINIMUM',
            'VDEF:global_avg_rx=avg_rx,AVERAGE',
            'VDEF:global_max_rx=max_rx,MAXIMUM',
            'VDEF:global_tot_rx=avg_rx_bytes,TOTAL',
            'CDEF:avg_tx_bytes=avg_tx,8,/',
            'VDEF:global_min_tx=min_tx,MINIMUM',
            'VDEF:global_avg_tx=avg_tx,AVERAGE',
            'VDEF:global_max_tx=max_tx,MAXIMUM',
            'VDEF:global_tot_tx=avg_tx_bytes,TOTAL',
            'CDEF:overlap=avg_rx,avg_tx,LT,avg_rx,avg_tx,IF',
            'AREA:avg_rx#bfbfff',
            'AREA:avg_tx#bfe0cf',
            'LINE1:avg_rx#0000ff:RX',
            'GPRINT:global_min_rx:%5.1lf%s Min.',
            'GPRINT:global_avg_rx:%5.1lf%s Avg.',
            'GPRINT:global_max_rx:%5.1lf%s Max.',
            'GPRINT:global_tot_rx:ca. %5.1lf%s Total\l',
            'LINE1:avg_tx#00b000:TX',
            'GPRINT:global_min_tx:%5.1lf%s Min.',
            'GPRINT:global_avg_tx:%5.1lf%s Avg.',
            'GPRINT:global_max_tx:%5.1lf%s Max.',
            'GPRINT:global_tot_tx:ca. %5.1lf%s Total\l'
        ]

        return args


class MemoryPlugin(RRDBase):

    title = "Physical memory utilization"
    vertical_label = "Bytes"

    def graph(self):

        memory_free = os.path.join(self.base_path, "memory-free.rrd")
        memory_active = os.path.join(self.base_path, "memory-active.rrd")
        memory_laundry = os.path.join(self.base_path, "memory-laundry.rrd")
        memory_inactive = os.path.join(self.base_path, "memory-inactive.rrd")
        memory_wired = os.path.join(self.base_path, "memory-wired.rrd")

        args = [
            'DEF:min0=%s:value:MIN' % memory_free,
            'DEF:avg0=%s:value:AVERAGE' % memory_free,
            'DEF:max0=%s:value:MAX' % memory_free,
            'DEF:min1=%s:value:MIN' % memory_active,
            'DEF:avg1=%s:value:AVERAGE' % memory_active,
            'DEF:max1=%s:value:MAX' % memory_active,
            'DEF:min2=%s:value:MIN' % memory_laundry,
            'DEF:avg2=%s:value:AVERAGE' % memory_laundry,
            'DEF:max2=%s:value:MAX' % memory_laundry,
            'DEF:min3=%s:value:MIN' % memory_inactive,
            'DEF:avg3=%s:value:AVERAGE' % memory_inactive,
            'DEF:max3=%s:value:MAX' % memory_inactive,
            'DEF:min4=%s:value:MIN' % memory_wired,
            'DEF:avg4=%s:value:AVERAGE' % memory_wired,
            'DEF:max4=%s:value:MAX' % memory_wired,
            'CDEF:cdef4=avg4,UN,0,avg4,IF',
            'CDEF:cdef3=avg3,UN,0,avg3,IF,cdef4,+',
            'CDEF:cdef2=avg2,UN,0,avg2,IF,cdef3,+',
            'CDEF:cdef1=avg1,UN,0,avg1,IF,cdef2,+',
            'CDEF:cdef0=avg0,UN,0,avg0,IF,cdef1,+',
            'AREA:cdef0#bfe0bfff',
            'AREA:cdef1#e0bfbf50',
            'AREA:cdef2#bfbfe040',
            'AREA:cdef3#bfe0e030',
            'AREA:cdef4#e0bfe020',
            'LINE1:cdef0#00a000:Free    ',
            'GPRINT:min0:MIN:%5.1lf%s Min,',
            'GPRINT:avg0:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max0:MAX:%5.1lf%s Max,',
            'GPRINT:avg0:LAST:%5.1lf%s Last\l',
            'LINE1:cdef1#a00000:Active  ',
            'GPRINT:min1:MIN:%5.1lf%s Min,',
            'GPRINT:avg1:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max1:MAX:%5.1lf%s Max,',
            'GPRINT:avg1:LAST:%5.1lf%s Last\l',
            'LINE1:cdef2#0000a0:Laundry ',
            'GPRINT:min2:MIN:%5.1lf%s Min,',
            'GPRINT:avg2:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max2:MAX:%5.1lf%s Max,',
            'GPRINT:avg2:LAST:%5.1lf%s Last\l',
            'LINE1:cdef3#00a0a0:Inactive',
            'GPRINT:min3:MIN:%5.1lf%s Min,',
            'GPRINT:avg3:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max3:MAX:%5.1lf%s Max,',
            'GPRINT:avg3:LAST:%5.1lf%s Last\l',
            'LINE1:cdef4#a000a0:Wired   ',
            'GPRINT:min4:MIN:%5.1lf%s Min,',
            'GPRINT:avg4:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max4:MAX:%5.1lf%s Max,',
            'GPRINT:avg4:LAST:%5.1lf%s Last\l'
        ]

        return args


class LoadPlugin(RRDBase):

    title = "System Load"
    vertical_label = "Processes"

    def graph(self):

        load = os.path.join(self.base_path, "load.rrd")

        args = [
            'DEF:s_min=%s:shortterm:MIN' % load,
            'DEF:s_avg=%s:shortterm:AVERAGE' % load,
            'DEF:s_max=%s:shortterm:MAX' % load,
            'DEF:m_min=%s:midterm:MIN' % load,
            'DEF:m_avg=%s:midterm:AVERAGE' % load,
            'DEF:m_max=%s:midterm:MAX' % load,
            'DEF:l_min=%s:longterm:MIN' % load,
            'DEF:l_avg=%s:longterm:AVERAGE' % load,
            'DEF:l_max=%s:longterm:MAX' % load,
            'AREA:s_max#bfffbf',
            'AREA:s_min#FFFFFF',
            'LINE1:s_avg#00ff00: 1 min',
            'GPRINT:s_min:MIN:%.2lf Min,',
            'GPRINT:s_avg:AVERAGE:%.2lf Avg,',
            'GPRINT:s_max:MAX:%.2lf Max,',
            'GPRINT:s_avg:LAST:%.2lf Last\l',
            'LINE1:m_avg#0000ff: 5 min',
            'GPRINT:m_min:MIN:%.2lf Min,',
            'GPRINT:m_avg:AVERAGE:%.2lf Avg,',
            'GPRINT:m_max:MAX:%.2lf Max,',
            'GPRINT:m_avg:LAST:%.2lf Last\l',
            'LINE1:l_avg#ff0000:15 min',
            'GPRINT:l_min:MIN:%.2lf Min,',
            'GPRINT:l_avg:AVERAGE:%.2lf Avg,',
            'GPRINT:l_max:MAX:%.2lf Max,',
            'GPRINT:l_avg:LAST:%.2lf Last\l'
        ]

        return args


class ProcessesPlugin(RRDBase):

    title = "Processes"
    vertical_label = "Processes"

    def graph(self):

        blocked = os.path.join(self.base_path, "ps_state-blocked.rrd")
        zombies = os.path.join(self.base_path, "ps_state-zombies.rrd")
        stopped = os.path.join(self.base_path, "ps_state-stopped.rrd")
        running = os.path.join(self.base_path, "ps_state-running.rrd")
        sleeping = os.path.join(self.base_path, "ps_state-sleeping.rrd")
        idle = os.path.join(self.base_path, "ps_state-idle.rrd")
        wait = os.path.join(self.base_path, "ps_state-wait.rrd")

        args = [
            'DEF:min0=%s:value:MIN' % blocked,
            'DEF:avg0=%s:value:AVERAGE' % blocked,
            'DEF:max0=%s:value:MAX' % blocked,
            'DEF:min1=%s:value:MIN' % zombies,
            'DEF:avg1=%s:value:AVERAGE' % zombies,
            'DEF:max1=%s:value:MAX' % zombies,
            'DEF:min2=%s:value:MIN' % stopped,
            'DEF:avg2=%s:value:AVERAGE' % stopped,
            'DEF:max2=%s:value:MAX' % stopped,
            'DEF:min3=%s:value:MIN' % running,
            'DEF:avg3=%s:value:AVERAGE' % running,
            'DEF:max3=%s:value:MAX' % running,
            'DEF:min4=%s:value:MIN' % sleeping,
            'DEF:avg4=%s:value:AVERAGE' % sleeping,
            'DEF:max4=%s:value:MAX' % sleeping,
            'DEF:min5=%s:value:MIN' % idle,
            'DEF:avg5=%s:value:AVERAGE' % idle,
            'DEF:max5=%s:value:MAX' % idle,
            'DEF:min6=%s:value:MIN' % wait,
            'DEF:avg6=%s:value:AVERAGE' % wait,
            'DEF:max6=%s:value:MAX' % wait,
            'CDEF:cdef6=avg6,UN,0,avg6,IF',
            'CDEF:cdef5=avg5,UN,0,avg5,IF,cdef6,+',
            'CDEF:cdef4=avg4,UN,0,avg4,IF,cdef5,+',
            'CDEF:cdef3=avg3,UN,0,avg3,IF,cdef4,+',
            'CDEF:cdef2=avg2,UN,0,avg2,IF,cdef3,+',
            'CDEF:cdef1=avg1,UN,0,avg1,IF,cdef2,+',
            'CDEF:cdef0=avg0,UN,0,avg0,IF,cdef1,+',
            'AREA:cdef0#ffbfff',
            'AREA:cdef1#ffbfbf',
            'AREA:cdef2#e7bfe7',
            'AREA:cdef3#bff7bf',
            'AREA:cdef4#bfbfff',
            'AREA:cdef5#bfbfbf',
            'AREA:cdef6#bfbfbf',
            'LINE1:cdef0#ff00ff:Blocked ',
            'GPRINT:min0:MIN:%5.1lf Min,',
            'GPRINT:avg0:AVERAGE:%5.1lf Avg,',
            'GPRINT:max0:MAX:%5.1lf Max,',
            'GPRINT:avg0:LAST:%5.1lf Last\l',
            'LINE1:cdef1#ff0000:Zombies ',
            'GPRINT:min1:MIN:%5.1lf Min,',
            'GPRINT:avg1:AVERAGE:%5.1lf Avg,',
            'GPRINT:max1:MAX:%5.1lf Max,',
            'GPRINT:avg1:LAST:%5.1lf Last\l',
            'LINE1:cdef2#a000a0:Stopped ',
            'GPRINT:min2:MIN:%5.1lf Min,',
            'GPRINT:avg2:AVERAGE:%5.1lf Avg,',
            'GPRINT:max2:MAX:%5.1lf Max,',
            'GPRINT:avg2:LAST:%5.1lf Last\l',
            'LINE1:cdef3#00e000:Running ',
            'GPRINT:min3:MIN:%5.1lf Min,',
            'GPRINT:avg3:AVERAGE:%5.1lf Avg,',
            'GPRINT:max3:MAX:%5.1lf Max,',
            'GPRINT:avg3:LAST:%5.1lf Last\l',
            'LINE1:cdef4#0000ff:Sleeping',
            'GPRINT:min4:MIN:%5.1lf Min,',
            'GPRINT:avg4:AVERAGE:%5.1lf Avg,',
            'GPRINT:max4:MAX:%5.1lf Max,',
            'GPRINT:avg4:LAST:%5.1lf Last\l',
            'LINE1:cdef5#000000:idle  ',
            'GPRINT:min5:MIN:%5.1lf Min,',
            'GPRINT:avg5:AVERAGE:%5.1lf Avg,',
            'GPRINT:max5:MAX:%5.1lf Max,',
            'GPRINT:avg5:LAST:%5.1lf Last\l',
            'LINE1:cdef6#000000:wait  ',
            'GPRINT:min6:MIN:%5.1lf Min,',
            'GPRINT:avg6:AVERAGE:%5.1lf Avg,',
            'GPRINT:max6:MAX:%5.1lf Max,',
            'GPRINT:avg6:LAST:%5.1lf Last\l'
        ]

        return args


class SwapPlugin(RRDBase):

    title = "Swap Utilization"
    vertical_label = "Bytes"

    def graph(self):

        free = os.path.join(self.base_path, "swap-free.rrd")
        used = os.path.join(self.base_path, "swap-used.rrd")

        args = [
            'DEF:min0=%s:value:MIN' % free,
            'DEF:avg0=%s:value:AVERAGE' % free,
            'DEF:max0=%s:value:MAX' % free,
            'DEF:min1=%s:value:MIN' % used,
            'DEF:avg1=%s:value:AVERAGE' % used,
            'DEF:max1=%s:value:MAX' % used,
            'CDEF:cdef1=avg1,UN,0,avg1,IF',
            'CDEF:cdef0=avg0,UN,0,avg0,IF,cdef1,+',
            'AREA:cdef0#bff7bf',
            'AREA:cdef1#ffbfbf',
            'LINE1:cdef0#00e000:Free  ',
            'GPRINT:min0:MIN:%5.1lf%s Min,',
            'GPRINT:avg0:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max0:MAX:%5.1lf%s Max,',
            'GPRINT:avg0:LAST:%5.1lf%s Last\l',
            'LINE1:cdef1#ff0000:Used  ',
            'GPRINT:min1:MIN:%5.1lf%s Min,',
            'GPRINT:avg1:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max1:MAX:%5.1lf%s Max,',
            'GPRINT:avg1:LAST:%5.1lf%s Last\l'
        ]

        return args


class DFPlugin(RRDBase):

    vertical_label = "Bytes"

    def get_title(self):
        title = self.identifier.replace("/mnt/", "")
        return 'Disk space (%s)' % title

    def encode(self, path):
        if path == "/":
            return "root"
        return path.strip('/').replace('/', '-')

    def get_identifiers(self):

        ids = []
        proc = pipeopen("/bin/df -t zfs", important=False, logger=log)
        for line in proc.communicate()[0].strip().split('\n'):
            entry = re.split(r'\s{2,}', line)[-1]
            if entry != "/" and not entry.startswith("/mnt"):
                continue
            path = os.path.join(self._base_path, "df-" + self.encode(entry), 'df_complex-free.rrd')
            if os.path.exists(path):
                ids.append(entry)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "df-%s" % self.encode(self.identifier))
        free = os.path.join(path, "df_complex-free.rrd")
        used = os.path.join(path, "df_complex-used.rrd")

        args = [
            'DEF:free_min=%s:value:MIN' % free,
            'DEF:free_avg=%s:value:AVERAGE' % free,
            'DEF:free_max=%s:value:MAX' % free,
            'DEF:used_min=%s:value:MIN' % used,
            'DEF:used_avg=%s:value:AVERAGE' % used,
            'DEF:used_max=%s:value:MAX' % used,
            'CDEF:both_avg=free_avg,used_avg,+',
            'AREA:both_avg#bfffbf',
            'AREA:used_avg#ffbfbf',
            'LINE1:both_avg#00ff00:Free',
            'GPRINT:free_min:MIN:%5.1lf%sB Min,',
            'GPRINT:free_avg:AVERAGE:%5.1lf%sB Avg,',
            'GPRINT:free_max:MAX:%5.1lf%sB Max,',
            'GPRINT:free_avg:LAST:%5.1lf%sB Last\l',
            'LINE1:used_avg#ff0000:Used',
            'GPRINT:used_min:MIN:%5.1lf%sB Min,',
            'GPRINT:used_avg:AVERAGE:%5.1lf%sB Avg,',
            'GPRINT:used_max:MAX:%5.1lf%sB Max,',
            'GPRINT:used_avg:LAST:%5.1lf%sB Last\l'
        ]

        return args


class UptimePlugin(RRDBase):

    title = "Uptime"
    vertical_label = "Days"

    def graph(self):

        path = os.path.join(self.base_path, "uptime.rrd")

        args = [
            'DEF:uptime_sec_avg=%s:value:AVERAGE' % path,
            'DEF:uptime_sec_max=%s:value:MAX' % path,
            'CDEF:uptime_no_unkn=uptime_sec_max,UN,0,uptime_sec_max,IF',
            'CDEF:uptime_peaks=uptime_no_unkn,PREV(uptime_no_unkn),LT,PREV(uptime_no_unkn),UNKN,IF',
            'VDEF:minimum_uptime_secs=uptime_peaks,MINIMUM',
            'CDEF:minimum_uptime_graph=uptime_sec_max,minimum_uptime_secs,EQ,uptime_sec_max,86400,/,0,IF',
            'CDEF:minimum_uptime_days=uptime_sec_max,minimum_uptime_secs,EQ,uptime_sec_max,86400,/,FLOOR,0,IF',
            'CDEF:minimum_uptime_hours=uptime_sec_max,minimum_uptime_secs,EQ,uptime_sec_max,86400,%,3600,/,FLOOR,0,IF',
            'CDEF:minimum_uptime_mins=uptime_sec_max,minimum_uptime_secs,EQ,uptime_sec_max,86400,%,3600,%,60,/,FLOOR,0,IF',
            'VDEF:min_uptime_graph=minimum_uptime_graph,MAXIMUM',
            'VDEF:min_uptime_days=minimum_uptime_days,MAXIMUM',
            'VDEF:min_uptime_hours=minimum_uptime_hours,MAXIMUM',
            'VDEF:min_uptime_mins=minimum_uptime_mins,MAXIMUM',
            'VDEF:maximum_uptime_secs=uptime_sec_max,MAXIMUM',
            'CDEF:maximum_uptime_graph=uptime_sec_max,maximum_uptime_secs,EQ,uptime_sec_max,86400,/,0,IF',
            'CDEF:maximum_uptime_days=uptime_sec_max,maximum_uptime_secs,EQ,uptime_sec_max,86400,/,FLOOR,0,IF',
            'CDEF:maximum_uptime_hours=uptime_sec_max,maximum_uptime_secs,EQ,uptime_sec_max,86400,%,3600,/,FLOOR,0,IF',
            'CDEF:maximum_uptime_mins=uptime_sec_max,maximum_uptime_secs,EQ,uptime_sec_max,86400,%,3600,%,60,/,FLOOR,0,IF',
            'VDEF:max_uptime_graph=maximum_uptime_graph,MAXIMUM',
            'VDEF:max_uptime_days=maximum_uptime_days,MAXIMUM',
            'VDEF:max_uptime_hours=maximum_uptime_hours,MAXIMUM',
            'VDEF:max_uptime_mins=maximum_uptime_mins,MAXIMUM',
            'VDEF:average_uptime_secs=uptime_sec_max,AVERAGE',
            'CDEF:average_uptime_graph=uptime_sec_max,POP,average_uptime_secs,86400,/',
            'CDEF:average_uptime_days=uptime_sec_max,POP,average_uptime_secs,86400,/,FLOOR',
            'CDEF:average_uptime_hours=uptime_sec_max,POP,average_uptime_secs,86400,%,3600,/,FLOOR',
            'CDEF:average_uptime_mins=uptime_sec_max,POP,average_uptime_secs,86400,%,3600,%,60,/,FLOOR',
            'VDEF:avg_uptime_days=average_uptime_days,LAST',
            'VDEF:avg_uptime_hours=average_uptime_hours,LAST',
            'VDEF:avg_uptime_mins=average_uptime_mins,LAST',
            'CDEF:current_uptime_graph=uptime_sec_max,86400,/',
            'CDEF:current_uptime_days=uptime_sec_max,86400,/,FLOOR',
            'CDEF:current_uptime_hours=uptime_sec_max,86400,%,3600,/,FLOOR',
            'CDEF:current_uptime_mins=uptime_sec_max,86400,%,3600,%,60,/,FLOOR',
            'VDEF:curr_uptime_days=current_uptime_days,LAST',
            'VDEF:curr_uptime_hours=current_uptime_hours,LAST',
            'VDEF:curr_uptime_mins=current_uptime_mins,LAST',
            'CDEF:time=uptime_sec_max,POP,TIME',
            'VDEF:start=time,FIRST',
            'VDEF:last=time,LAST',
            'CDEF:time_window=uptime_sec_max,UN,0,uptime_sec_max,IF,POP,TIME',
            'CDEF:time_window2=PREV(time_window)',
            'VDEF:window_start=time_window,FIRST',
            'VDEF:window_last=time_window,LAST',
            'CDEF:delta=uptime_sec_max,POP,window_last,window_start,-',
            'CDEF:system_on_un=uptime_sec_avg,UN,UNKN,1,IF',
            'CDEF:system_on=PREV(system_on_un),1,EQ,system_on_un,POP,TIME,window_last,EQ,*,1,system_on_un,IF',
            'VDEF:new_average_on=system_on,AVERAGE',
            'VDEF:total_uptime_secs=system_on_un,TOTAL',
            'CDEF:total_uptime_days=uptime_sec_max,POP,total_uptime_secs,86400,/,FLOOR',
            'CDEF:total_uptime_hours=uptime_sec_max,POP,total_uptime_secs,86400,%,3600,/,FLOOR',
            'CDEF:total_uptime_mins=uptime_sec_max,POP,total_uptime_secs,86400,%,3600,%,60,/,FLOOR',
            'VDEF:tot_uptime_days=total_uptime_days,LAST',
            'VDEF:tot_uptime_hours=total_uptime_hours,LAST',
            'VDEF:tot_uptime_mins=total_uptime_mins,LAST',
            'CDEF:temp_perc_on=uptime_sec_max,POP,total_uptime_secs,delta,/,100,*',
            'VDEF:new_perc_on=temp_perc_on,LAST',
            'COMMENT:\s',
            'COMMENT:  ',
            'AREA:current_uptime_graph#66666640',
            'LINE1:current_uptime_graph#F17742:Current\:',
            'GPRINT:curr_uptime_days:%5.0lf days',
            'GPRINT:curr_uptime_hours:%3.0lf hours',
            'GPRINT:curr_uptime_mins:%3.0lf mins',
            'COMMENT:\\n',
            'COMMENT:  ',
            'LINE1:max_uptime_graph#DA1F3D:Maximum\::dashes',
            'GPRINT:max_uptime_days:%5.0lf days',
            'GPRINT:max_uptime_hours:%3.0lf hours',
            'GPRINT:max_uptime_mins:%3.0lf mins',
            'COMMENT:\\n',
            'COMMENT:  ',
            'HRULE:min_uptime_graph#FCE053:Minimum\::dashes',
            'GPRINT:min_uptime_days:%5.0lf days',
            'GPRINT:min_uptime_hours:%3.0lf hours',
            'GPRINT:min_uptime_mins:%3.0lf mins',
            'COMMENT:\\n',
            'COMMENT:  ',
            'LINE1:average_uptime_graph#6CABE7:Average\::dashes',
            'GPRINT:avg_uptime_days:%5.0lf days',
            'GPRINT:avg_uptime_hours:%3.0lf hours',
            'GPRINT:avg_uptime_mins:%3.0lf mins',
            'COMMENT:\\n',
            'COMMENT:    Total run\:',
            'GPRINT:tot_uptime_days:%5.0lf days',
            'GPRINT:tot_uptime_hours:%3.0lf hours',
            'GPRINT:tot_uptime_mins:%3.0lf mins  ',
            'COMMENT:\\n',
            'PRINT:new_perc_on:%lf %%',
            'PRINT:total_uptime_secs:%lf secs',
            'PRINT:new_average_on:%lf %%',
            'COMMENT:\s'
        ]

        return args


class CTLPlugin(RRDBase):

    vertical_label = "Bytes/s"

    def get_title(self):
        title = self.identifier.replace("ctl-", "")
        return 'SCSI target port (%s)' % title

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/ctl-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
#            if not os.path.exists('/dev/%s' % ident):
#                continue
            if ident.endswith('ioctl'):
                continue
            if os.path.exists(os.path.join(entry, 'disk_octets.rrd')):
                ids.append(ident)

        ids.sort(key=RRDBase._sort_ports)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "ctl-%s" % self.identifier.replace(":", "\:"), "disk_octets.rrd")

        args = [
            'DEF:min_rd=%s:read:MIN' % path,
            'DEF:avg_rd=%s:read:AVERAGE' % path,
            'DEF:max_rd=%s:read:MAX' % path,
            'DEF:min_wr=%s:write:MIN' % path,
            'DEF:avg_wr=%s:write:AVERAGE' % path,
            'DEF:max_wr=%s:write:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'VDEF:tot_wr=avg_wr,TOTAL',
            'AREA:avg_rd#bfbfff',
            'AREA:avg_wr#bfe0cf',
            'LINE1:avg_rd#0000ff:Read ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
            'LINE1:avg_wr#00b000:Write',
            'GPRINT:min_wr:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_wr:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_wr:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_wr:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_wr: %3.0lf%s Total\l',
        ]

        return args


@cache_with_autorefresh(0, 5)
def get_disks():
    with client as c:
        return c.call('disk.query')


class DiskBase():
    def get_disk_description(self, name):
        disk_desc = ''
        try:
            disk_desc = filter_list(get_disks(), [('name', '=', name)], {'get': True})['description']
        except BaseException as error:
            # it would be lame to fail just coz we could not get disk description
            # but lets log it
            log.debug(f'Failed to get disk description of disk: {name}', exc_info=True)
        return f'Disk description: {disk_desc}' if disk_desc else ''


class DiskPlugin(RRDBase, DiskBase):

    vertical_label = "Bytes/s"

    def get_title(self):
        title = self.identifier.replace("disk-", "")
        return f'Disk I/O ({title}) Description: {self.get_disk_description(title)}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/disk-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass'):
                continue
            if os.path.exists(os.path.join(entry, 'disk_octets.rrd')):
                ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "disk-%s" % self.identifier, "disk_octets.rrd")

        args = [
            'DEF:min_rd=%s:read:MIN' % path,
            'DEF:avg_rd=%s:read:AVERAGE' % path,
            'DEF:max_rd=%s:read:MAX' % path,
            'DEF:min_wr=%s:write:MIN' % path,
            'DEF:avg_wr=%s:write:AVERAGE' % path,
            'DEF:max_wr=%s:write:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'VDEF:tot_wr=avg_wr,TOTAL',
            'AREA:avg_rd#bfbfff',
            'AREA:avg_wr#bfe0cf',
            'LINE1:avg_rd#0000ff:Read ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
            'LINE1:avg_wr#00b000:Write',
            'GPRINT:min_wr:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_wr:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_wr:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_wr:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_wr: %3.0lf%s Total\l',
        ]

        return args


class DiskGeomBusyPlugin(RRDBase, DiskBase):

    vertical_label = "Percent"

    def get_title(self):
        title = self.identifier.replace("geom_stat/geom_busy_percent-", "")
        return f'Disk Busy ({title}) {self.get_disk_description(title)}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/geom_stat/geom_busy_percent-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            ident = re.sub(r'.rrd$', '', ident)
            if not re.match(r'^[a-z]+[0-9]+$', ident):
                continue
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "geom_stat/geom_busy_percent-%s.rrd" % self.identifier)

        args = [
            'DEF:min_rd=%s:value:MIN' % path,
            'DEF:avg_rd=%s:value:AVERAGE' % path,
            'DEF:max_rd=%s:value:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'AREA:avg_rd#bfbfff',
            'LINE1:avg_rd#0000ff:Value ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
        ]

        return args


class DiskGeomLatencyPlugin(RRDBase, DiskBase):

    vertical_label = "Time,msec"

    def get_title(self):
        title = self.identifier.replace("geom_stat/geom_latency-", "")
        return f'Disk Latency ({title}) {self.get_disk_description(title)}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/geom_stat/geom_latency-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            ident = re.sub(r'.rrd$', '', ident)
            if not re.match(r'^[a-z]+[0-9]+$', ident):
                continue
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "geom_stat/geom_latency-%s.rrd" % self.identifier)

        args = [
            'DEF:min_rd=%s:read:MIN' % path,
            'DEF:avg_rd=%s:read:AVERAGE' % path,
            'DEF:max_rd=%s:read:MAX' % path,
            'DEF:min_wr=%s:write:MIN' % path,
            'DEF:avg_wr=%s:write:AVERAGE' % path,
            'DEF:max_wr=%s:write:MAX' % path,
            'DEF:min_dl=%s:delete:MIN' % path,
            'DEF:avg_dl=%s:delete:AVERAGE' % path,
            'DEF:max_dl=%s:delete:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'VDEF:tot_wr=avg_wr,TOTAL',
            'VDEF:tot_dl=avg_dl,TOTAL',
            'AREA:avg_rd#bfbfff',
            'AREA:avg_wr#bfe0cf',
            'AREA:avg_dl#ffe0bf',
            'LINE1:avg_rd#0000ff:Read  ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
            'LINE1:avg_wr#00b000:Write ',
            'GPRINT:min_wr:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_wr:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_wr:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_wr:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_wr: %3.0lf%s Total\l',
            'LINE1:avg_dl#ff0000:Delete',
            'GPRINT:min_dl:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_dl:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_dl:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_dl:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_dl: %3.0lf%s Total\l',
        ]

        return args


class DiskGeomOpsRWDPlugin(RRDBase, DiskBase):

    vertical_label = "Operations/s"

    def get_title(self):
        title = self.identifier.replace("geom_stat/geom_ops_rwd-", "")
        return f'Disk Operations detailed ({title}) {self.get_disk_description(title)}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/geom_stat/geom_ops_rwd-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            ident = re.sub(r'.rrd$', '', ident)
            if not re.match(r'^[a-z]+[0-9]+$', ident):
                continue
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "geom_stat/geom_ops_rwd-%s.rrd" % self.identifier)

        args = [
            'DEF:min_rd=%s:read:MIN' % path,
            'DEF:avg_rd=%s:read:AVERAGE' % path,
            'DEF:max_rd=%s:read:MAX' % path,
            'DEF:min_wr=%s:write:MIN' % path,
            'DEF:avg_wr=%s:write:AVERAGE' % path,
            'DEF:max_wr=%s:write:MAX' % path,
            'DEF:min_dl=%s:delete:MIN' % path,
            'DEF:avg_dl=%s:delete:AVERAGE' % path,
            'DEF:max_dl=%s:delete:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'VDEF:tot_wr=avg_wr,TOTAL',
            'VDEF:tot_dl=avg_dl,TOTAL',
            'AREA:avg_rd#bfbfff',
            'AREA:avg_wr#bfe0cf',
            'AREA:avg_dl#ffe0bf',
            'LINE1:avg_rd#0000ff:Read  ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
            'LINE1:avg_wr#00b000:Write ',
            'GPRINT:min_wr:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_wr:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_wr:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_wr:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_wr: %3.0lf%s Total\l',
            'LINE1:avg_dl#ff0000:Delete',
            'GPRINT:min_dl:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_dl:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_dl:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_dl:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_dl: %3.0lf%s Total\l',
        ]

        return args


class DiskGeomQueuePlugin(RRDBase, DiskBase):

    vertical_label = "Requests"

    def get_title(self):
        title = self.identifier.replace("geom_stat/geom_queue-", "")
        return f'Pending I/O requests on ({title}) {self.get_disk_description(title)}'

    def get_identifiers(self):
        ids = []
        for entry in glob.glob('%s/geom_stat/geom_queue-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            ident = re.sub(r'.rrd$', '', ident)
            if not re.match(r'^[a-z]+[0-9]+$', ident):
                continue
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_disks)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "geom_stat/geom_queue-%s.rrd" % self.identifier)

        args = [
            'DEF:min_rd=%s:length:MIN' % path,
            'DEF:avg_rd=%s:length:AVERAGE' % path,
            'DEF:max_rd=%s:length:MAX' % path,
            'VDEF:tot_rd=avg_rd,TOTAL',
            'AREA:avg_rd#bfbfff',
            'LINE1:avg_rd#0000ff:I/O Requests ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_rd: %3.0lf%s Total\l',
        ]

        return args


class ARCSizePlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = "Bytes"

    def get_title(self):
        return 'ARC Size'

    def graph(self):

        cachearc = os.path.join(self.base_path, "cache_size-arc.rrd")
        cachel2 = os.path.join(self.base_path, "cache_size-L2.rrd")

        args = [
            'DEF:arc_size=%s:value:MAX' % cachearc,
            'DEF:l2arc_size=%s:value:MAX' % cachel2,
            'LINE1:arc_size#0000FF:ARC  ',
            'GPRINT:arc_size:MIN:%5.1lf%s Min\g',
            'GPRINT:arc_size:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:arc_size:MAX: %5.1lf%s Max\g',
            'GPRINT:arc_size:LAST: %5.1lf%s Last\l',
            'LINE1:l2arc_size#FF0000:L2ARC',
            'GPRINT:l2arc_size:MIN:%5.1lf%s Min\g',
            'GPRINT:l2arc_size:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:l2arc_size:MAX: %5.1lf%s Max\g',
            'GPRINT:l2arc_size:LAST: %5.1lf%s Last\l',
        ]

        return args


class ARCRatioPlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = "Hits (%)"

    def get_title(self):
        return 'ARC Hit Ratio'

    def graph(self):

        ratioarc = os.path.join(self.base_path, "cache_ratio-arc.rrd")
        ratiol2 = os.path.join(self.base_path, "cache_ratio-L2.rrd")

        args = [
            'DEF:arc_hit=%s:value:MAX' % ratioarc,
            'CDEF:arc_p=arc_hit,100,*',
            'DEF:l2arc_hit=%s:value:MAX' % ratiol2,
            'CDEF:l2arc_p=l2arc_hit,100,*',
            'LINE1:arc_p#0000FF:ARC  ',
            'GPRINT:arc_p:MIN:%5.1lf%% Min\g',
            'GPRINT:arc_p:AVERAGE: %5.1lf%% Avg\g',
            'GPRINT:arc_p:MAX: %5.1lf%% Max\g',
            'GPRINT:arc_p:LAST: %5.1lf%% Last\l',
            'LINE1:l2arc_p#FF0000:L2ARC',
            'GPRINT:l2arc_p:MIN:%5.1lf%% Min\g',
            'GPRINT:l2arc_p:AVERAGE: %5.1lf%% Avg\g',
            'GPRINT:l2arc_p:MAX: %5.1lf%% Max\g',
            'GPRINT:l2arc_p:LAST: %5.1lf%% Last\l',
        ]

        return args


class ARCResultPlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = "Requests"

    def get_title(self):
        return 'ARC Requests (%s)' % self.identifier

    def get_identifiers(self):
        return ("demand_data", "demand_metadata", "prefetch_data", "prefetch_metadata")

    def graph(self):

        hit = os.path.join(self.base_path, "cache_result-%s-hit.rrd" % self.identifier)
        miss = os.path.join(self.base_path, "cache_result-%s-miss.rrd" % self.identifier)

        args = [
            'DEF:min_h=%s:value:MIN' % hit,
            'DEF:avg_h=%s:value:AVERAGE' % hit,
            'DEF:max_h=%s:value:MAX' % hit,
            'DEF:min_m=%s:value:MIN' % miss,
            'DEF:avg_m=%s:value:AVERAGE' % miss,
            'DEF:max_m=%s:value:MAX' % miss,
            'CDEF:min_t=min_h,min_m,+',
            'CDEF:avg_t=avg_h,avg_m,+',
            'CDEF:max_t=max_h,max_m,+',
            'VDEF:tot_t=avg_t,TOTAL',
            'VDEF:tot_h=avg_h,TOTAL',
            'AREA:avg_t#ffbfbf',
            'AREA:avg_h#bfbfff',
            'LINE1:avg_t#ff0000:Total',
            'GPRINT:min_t:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_t:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_t:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_t:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_t: %3.0lf%s Total\l',
            'LINE1:avg_h#0000ff:Hit  ',
            'GPRINT:min_h:MIN:%5.1lf%s Min\g',
            'GPRINT:avg_h:AVERAGE: %5.1lf%s Avg\g',
            'GPRINT:max_h:MAX: %5.1lf%s Max\g',
            'GPRINT:avg_h:LAST: %5.1lf%s Last\g',
            'GPRINT:tot_h: %3.0lf%s Total\l',
        ]

        return args


class NFSStatPlugin(RRDBase):

    title = "NFS Stats"
    vertical_label = "Bytes"

    def graph(self):

        read = os.path.join(f'{self.base_path}-client', 'nfsstat-read.rrd')
        write = os.path.join(f'{self.base_path}-client', 'nfsstat-write.rrd')

        args = [
            f'DEF:min_read={read}:value:MIN',
            f'DEF:avg_read={read}:value:AVERAGE',
            f'DEF:max_read={read}:value:MAX',
            f'DEF:min_write={write}:value:MIN',
            f'DEF:avg_write={write}:value:AVERAGE',
            f'DEF:max_write={write}:value:MAX',
            'VDEF:total_read=avg_read,TOTAL',
            'VDEF:total_write=avg_write,TOTAL',
            'CDEF:read=avg_read',
            'CDEF:write=avg_write',
            'AREA:read#bfbfff',
            'LINE1:read#bfbfff:Read',
            r'GPRINT:min_read:MIN:%5.1lf%s Min\g',
            r'GPRINT:avg_read:AVERAGE: %5.1lf%s Avg\g',
            r'GPRINT:max_read:MAX: %5.1lf%s Max\g',
            r'GPRINT:avg_read:LAST: %5.1lf%s Last\g',
            r'GPRINT:total_read: %3.0lf%s Total\l',
            'AREA:write#00b000',
            'LINE1:write#00b000:Write',
            r'GPRINT:min_write:MIN:%5.1lf%s Min\g',
            r'GPRINT:avg_write:AVERAGE: %5.1lf%s Avg\g',
            r'GPRINT:max_write:MAX: %5.1lf%s Max\g',
            r'GPRINT:avg_write:LAST: %5.1lf%s Last\g',
            r'GPRINT:total_write: %3.0lf%s Total\l',
        ]

        return args


class UPSBatteryChargePlugin(RRDBase, DiskBase):

    title = 'UPS Battery Charge'
    vertical_label = 'Percent'

    def graph(self):

        path = os.path.join(self._base_path, 'nut-ups/percent-charge.rrd')

        args = [
            f'DEF:min_rd={path}:value:MIN',
            f'DEF:avg_rd={path}:value:AVERAGE',
            f'DEF:max_rd={path}:value:MAX',
            'VDEF:tot_rd=avg_rd,TOTAL',
            'AREA:avg_rd#bfbfff',
            'LINE1:avg_rd#0000ff:Value ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\\g',
            'GPRINT:tot_rd: %3.0lf%s Total\\l',
        ]

        return args


class UPSRemainingBatteryPlugin(RRDBase, DiskBase):

    title = 'UPS Remaining Battery Statistics'
    vertical_label = 'Seconds'

    def graph(self):

        path = os.path.join(self._base_path, 'nut-ups/timeleft-battery.rrd')

        args = [
            f'DEF:min_rd={path}:value:MIN',
            f'DEF:avg_rd={path}:value:AVERAGE',
            f'DEF:max_rd={path}:value:MAX',
            'VDEF:tot_rd=avg_rd,TOTAL',
            'AREA:avg_rd#bfbfff',
            'LINE1:avg_rd#0000ff:Value ',
            'GPRINT:min_rd:MIN:%5.1lf%s Min\\g',
            'GPRINT:avg_rd:AVERAGE: %5.1lf%s Avg\\g',
            'GPRINT:max_rd:MAX: %5.1lf%s Max\\g',
            'GPRINT:avg_rd:LAST: %5.1lf%s Last\\g',
            'GPRINT:tot_rd: %3.0lf%s Total\\l',
        ]

        return args
