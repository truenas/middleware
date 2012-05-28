#+
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
import logging
import os
import re
import tempfile

import rrdtool

RRD_BASE_PATH = "/var/db/collectd/rrd/localhost"

log = logging.getLogger('reporting.rrd')

name2plugin = dict()


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = re.search(r'^(?P<name>.+)Plugin$', name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group("name").lower()
            klass.base_path = os.path.join(RRD_BASE_PATH, klass.plugin)
            name2plugin[klass.plugin] = klass
        elif hasattr(klass, 'plugin'):
            name2plugin[klass.plugin] = klass
        return klass


class RRDBase(object):

    __metaclass__ = RRDMeta

    identifier = None
    title = None
    vertical_label = None
    imgformat = 'PNG'
    unit = 'hourly'
    step = 0

    def __init__(self, identifier=None, unit=None, step=None):
        if identifier is not None:
            self.identifier = str(identifier)
        if unit is not None:
            self.unit = str(unit)
        if step is not None:
            self.step = int(step)

    def __repr__(self):
        return '<RRD:%s>' % self.plugin

    def graph(self):
        raise NotImplementedError

    def get_title(self):
        return self.title

    def get_vertical_label(self):
        return self.vertical_label

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
            path,
            '--imgformat', self.imgformat,
            '--vertical-label', str(self.get_vertical_label()),
            '--title', str(self.get_title()),
            '--lower-limit', '0',
            '--end', endtime,
            '--start', 'end-%s' % starttime, '-b', '1024',
        ]
        args.extend(self.graph())
        rrdtool.graph(*args)
        return path


class CPUPlugin(RRDBase):

    plugin = "cpu-0"
    title = "CPU Usage"
    vertical_label = "%CPU"

    def graph(self):
        cpu_idle = os.path.join(RRD_BASE_PATH, "cpu-0/cpu-idle.rrd")
        cpu_nice = os.path.join(RRD_BASE_PATH, "cpu-0/cpu-nice.rrd")
        cpu_user = os.path.join(RRD_BASE_PATH, "cpu-0/cpu-user.rrd")
        cpu_system = os.path.join(RRD_BASE_PATH, "cpu-0/cpu-system.rrd")
        cpu_interrupt = os.path.join(RRD_BASE_PATH, "cpu-0/cpu-interrupt.rrd")

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
            'GPRINT:min0:MIN:%5.2lf Min,',
            'GPRINT:avg0:AVERAGE:%5.2lf Avg,',
            'GPRINT:max0:MAX:%5.2lf Max,',
            'GPRINT:avg0:LAST:%5.2lf Last\l',
            'LINE1:cdef1#00e000:Nice  ',
            'GPRINT:min1:MIN:%5.2lf Min,',
            'GPRINT:avg1:AVERAGE:%5.2lf Avg,',
            'GPRINT:max1:MAX:%5.2lf Max,',
            'GPRINT:avg1:LAST:%5.2lf Last\l',
            'LINE1:cdef2#0000ff:User  ',
            'GPRINT:min2:MIN:%5.2lf Min,',
            'GPRINT:avg2:AVERAGE:%5.2lf Avg,',
            'GPRINT:max2:MAX:%5.2lf Max,',
            'GPRINT:avg2:LAST:%5.2lf Last\l',
            'LINE1:cdef3#ff0000:System',
            'GPRINT:min3:MIN:%5.2lf Min,',
            'GPRINT:avg3:AVERAGE:%5.2lf Avg,',
            'GPRINT:max3:MAX:%5.2lf Max,',
            'GPRINT:avg3:LAST:%5.2lf Last\l',
            'LINE1:cdef4#a000a0:IRQ   ',
            'GPRINT:min4:MIN:%5.2lf Min,',
            'GPRINT:avg4:AVERAGE:%5.2lf Avg,',
            'GPRINT:max4:MAX:%5.2lf Max,',
            'GPRINT:avg4:LAST:%5.2lf Last\l',
        ]

        return args


class InterfacePlugin(RRDBase):

    vertical_label = "Bits per second"

    def get_title(self):
        return 'Interface Traffic (%s)' % self.identifier

    def graph(self):
        path = os.path.join(
            self.base_path,
            "if_octets-%s.rrd" % self.identifier
            )

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
        memory_cache = os.path.join(self.base_path, "memory-cache.rrd")
        memory_inactive = os.path.join(self.base_path, "memory-inactive.rrd")
        memory_wired = os.path.join(self.base_path, "memory-wired.rrd")

        args = [
            'DEF:min0=%s:value:MIN' % memory_free,
            'DEF:avg0=%s:value:AVERAGE' % memory_free,
            'DEF:max0=%s:value:MAX' % memory_free,
            'DEF:min1=%s:value:MIN' % memory_active,
            'DEF:avg1=%s:value:AVERAGE' % memory_active,
            'DEF:max1=%s:value:MAX' % memory_active,
            'DEF:min2=%s:value:MIN' % memory_cache,
            'DEF:avg2=%s:value:AVERAGE' % memory_cache,
            'DEF:max2=%s:value:MAX' % memory_cache,
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
            'LINE1:cdef0#00a000:Free  ',
            'GPRINT:min0:MIN:%5.1lf%s Min,',
            'GPRINT:avg0:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max0:MAX:%5.1lf%s Max,',
            'GPRINT:avg0:LAST:%5.1lf%s Last\l',
            'LINE1:cdef1#a00000:Active  ',
            'GPRINT:min1:MIN:%5.1lf%s Min,',
            'GPRINT:avg1:AVERAGE:%5.1lf%s Avg,',
            'GPRINT:max1:MAX:%5.1lf%s Max,',
            'GPRINT:avg1:LAST:%5.1lf%s Last\l',
            'LINE1:cdef2#0000a0:Cache   ',
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
    vertical_label = "System Load"

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
        title = title.replace("mnt-", "")
        return 'Diskspace (%s)' % title

    def graph(self):

        path = os.path.join(self.base_path, "df-%s.rrd" % self.identifier)

        args = [
            'DEF:free_min=%s:free:MIN' % path,
            'DEF:free_avg=%s:free:AVERAGE' % path,
            'DEF:free_max=%s:free:MAX' % path,
            'DEF:used_min=%s:used:MIN' % path,
            'DEF:used_avg=%s:used:AVERAGE' % path,
            'DEF:used_max=%s:used:MAX' % path,
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
