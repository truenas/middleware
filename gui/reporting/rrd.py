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
import glob
import logging
import os
import re
import tempfile
import subprocess

from freenasUI.common.pipesubr import pipeopen

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


class RRDBase(object):

    __metaclass__ = RRDMeta

    base_path = None
    identifier = None
    title = None
    vertical_label = None
    imgformat = 'PNG'
    unit = 'hourly'
    step = 0
    sources = {}

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
    def _sort_identifiers(entry):
        reg = re.search('(.+)(\d+)$', entry)
        if not reg:
            return entry
        if reg:
            return (reg.group(1), int(reg.group(2)))

    def get_identifiers(self):
        return None

    def get_sources(self):
        return self.sources

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
    sources = {
        'localhost.aggregation-cpu-sum.cpu-interrupt.value': {
            'verbose_name': 'Interrupt',
        },
        'localhost.aggregation-cpu-sum.cpu-user.value': {
            'verbose_name': 'User',
        },
        'localhost.aggregation-cpu-sum.cpu-idle.value': {
            'verbose_name': 'Idle',
        },
        'localhost.aggregation-cpu-sum.cpu-system.value': {
            'verbose_name': 'System',
        },
        'localhost.aggregation-cpu-sum.cpu-nice.value': {
            'verbose_name': 'Nice',
        },
    }


class InterfacePlugin(RRDBase):

    vertical_label = "Bits per second"

    def get_title(self):
        return 'Interface Traffic (%s)' % self.identifier

    def get_identifiers(self):
        from freenasUI.middleware.connector import connection as dispatcher
        sources = dispatcher.call_sync('statd.output.get_data_sources')
        ids = []
        for source in sources:
            name = source.split('.')
            if len(name) < 3:
                continue
            if not name[1].startswith('interface'):
                continue
            ident = name[1].split('-', 1)[-1]
            if ident in ids:
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_identifiers)
        return ids

    def get_sources(self):
        return {
            'localhost.interface-%s.if_octets.rx' % self.identifier: {
                'verbose_name': 'Download',
            },
            'localhost.interface-%s.if_octets.tx' % self.identifier: {
                'verbose_name': 'Upload',
            },
        }


class MemoryPlugin(RRDBase):

    title = "Physical memory utilization"
    vertical_label = "Bytes"
    sources = {
        'localhost.memory.memory-active.value': {
            'verbose_name': 'Active',
        },
        'localhost.memory.memory-cache.value': {
            'verbose_name': 'Cache',
        },
        'localhost.memory.memory-free.value': {
            'verbose_name': 'Free',
        },
        'localhost.memory.memory-inactive.value': {
            'verbose_name': 'Inactive',
        },
        'localhost.memory.memory-wired.value': {
            'verbose_name': 'Wired',
        },
    }


class LoadPlugin(RRDBase):

    title = "System Load"
    vertical_label = "System Load"
    sources = {
        'localhost.load.load.shortterm': {
            'verbose_name': 'Short Term',
        },
        'localhost.load.load.midterm': {
            'verbose_name': 'Mid Term',
        },
        'localhost.load.load.longterm': {
            'verbose_name': 'Long Term',
        },
    }


class ProcessesPlugin(RRDBase):

    title = "Processes"
    vertical_label = "Processes"
    sources = {
        'localhost.processes.ps_state-blocked.value': {
            'verbose_name': 'Blocked',
        },
        'localhost.processes.ps_state-idle.value': {
            'verbose_name': 'Idle',
        },
        'localhost.processes.ps_state-running.value': {
            'verbose_name': 'Running',
        },
        'localhost.processes.ps_state-sleeping.value': {
            'verbose_name': 'Sleeping',
        },
        'localhost.processes.ps_state-stopped.value': {
            'verbose_name': 'Stopped',
        },
        'localhost.processes.ps_state-wait.value': {
            'verbose_name': 'Wait',
        },
        'localhost.processes.ps_state-zombies.value': {
            'verbose_name': 'Zombies',
        },
    }


class SwapPlugin(RRDBase):

    title = "Swap Utilization"
    vertical_label = "Bytes"
    sources = {
        'localhost.swap.swap-free.value': {
            'verbose_name': 'Free',
        },
        'localhost.swap.swap-used.value': {
            'verbose_name': 'Used',
        },
    }


class DFPlugin(RRDBase):

    vertical_label = "Bytes"

    def _get_mountpoints(self):
        mps = []
        proc = pipeopen("/bin/df -l", important=False, logger=log)
        for line in proc.communicate()[0].strip().split('\n'):
            mps.append(re.split(r'\s{2,}', line)[-1].replace('/', '-'))
        return mps

    def get_title(self):
        title = self.identifier.replace("mnt-", "")
        return 'Diskspace (%s)' % title

    def get_identifiers(self):

        mps = self._get_mountpoints()
        ids = []
        for entry in glob.glob('%s/df-*' % self._base_path):
            ident = entry.split('-', 1)[-1]
            if '-%s' % ident not in mps:
                continue
            if not ident.startswith("mnt"):
                continue
            if os.path.exists(os.path.join(entry, 'df_complex-free.rrd')):
                ids.append(ident)
        return ids

    def graph(self):

        path = os.path.join(self._base_path, "df-%s" % self.identifier)
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
    vertical_label = "Time"

    def graph(self):

        path = os.path.join(self.base_path, "uptime.rrd")

        args = [
            'DEF:uptime_sec_avg=%s:value:AVERAGE' % path,
            'DEF:uptime_sec_max=%s:value:MAX' % path,
            'CDEF:uptime_no_unkn=uptime_sec_max,UN,0,uptime_sec_max,IF',
            'CDEF:uptime_peaks=uptime_no_unkn,PREV(uptime_no_unkn),LT,'
                'PREV(uptime_no_unkn),UNKN,IF',
            'VDEF:minimum_uptime_secs=uptime_peaks,MINIMUM',
            'CDEF:minimum_uptime_graph=uptime_sec_max,minimum_uptime_secs,EQ,'
                'uptime_sec_max,86400,/,0,IF',
            'CDEF:minimum_uptime_days=uptime_sec_max,minimum_uptime_secs,EQ,'
                'uptime_sec_max,86400,/,FLOOR,0,IF',
            'CDEF:minimum_uptime_hours=uptime_sec_max,minimum_uptime_secs,EQ,'
                'uptime_sec_max,86400,%,3600,/,FLOOR,0,IF',
            'CDEF:minimum_uptime_mins=uptime_sec_max,minimum_uptime_secs,EQ,'
                'uptime_sec_max,86400,%,3600,%,60,/,FLOOR,0,IF',
            'VDEF:min_uptime_graph=minimum_uptime_graph,MAXIMUM',
            'VDEF:min_uptime_days=minimum_uptime_days,MAXIMUM',
            'VDEF:min_uptime_hours=minimum_uptime_hours,MAXIMUM',
            'VDEF:min_uptime_mins=minimum_uptime_mins,MAXIMUM',
            'VDEF:maximum_uptime_secs=uptime_sec_max,MAXIMUM',
            'CDEF:maximum_uptime_graph=uptime_sec_max,maximum_uptime_secs,EQ,'
                'uptime_sec_max,86400,/,0,IF',
            'CDEF:maximum_uptime_days=uptime_sec_max,maximum_uptime_secs,EQ,'
                'uptime_sec_max,86400,/,FLOOR,0,IF',
            'CDEF:maximum_uptime_hours=uptime_sec_max,maximum_uptime_secs,EQ,'
                'uptime_sec_max,86400,%,3600,/,FLOOR,0,IF',
            'CDEF:maximum_uptime_mins=uptime_sec_max,maximum_uptime_secs,EQ,'
                'uptime_sec_max,86400,%,3600,%,60,/,FLOOR,0,IF',
            'VDEF:max_uptime_graph=maximum_uptime_graph,MAXIMUM',
            'VDEF:max_uptime_days=maximum_uptime_days,MAXIMUM',
            'VDEF:max_uptime_hours=maximum_uptime_hours,MAXIMUM',
            'VDEF:max_uptime_mins=maximum_uptime_mins,MAXIMUM',
            'VDEF:average_uptime_secs=uptime_sec_max,AVERAGE',
            'CDEF:average_uptime_graph=uptime_sec_max,POP,average_uptime_secs,'
                '86400,/',
            'CDEF:average_uptime_days=uptime_sec_max,POP,average_uptime_secs,'
                '86400,/,FLOOR',
            'CDEF:average_uptime_hours=uptime_sec_max,POP,average_uptime_secs,'
                '86400,%,3600,/,FLOOR',
            'CDEF:average_uptime_mins=uptime_sec_max,POP,average_uptime_secs,'
                '86400,%,3600,%,60,/,FLOOR',
            'VDEF:avg_uptime_days=average_uptime_days,LAST',
            'VDEF:avg_uptime_hours=average_uptime_hours,LAST',
            'VDEF:avg_uptime_mins=average_uptime_mins,LAST',
            'CDEF:current_uptime_graph=uptime_sec_max,86400,/',
            'CDEF:current_uptime_days=uptime_sec_max,86400,/,FLOOR',
            'CDEF:current_uptime_hours=uptime_sec_max,86400,%,3600,/,FLOOR',
            'CDEF:current_uptime_mins=uptime_sec_max,86400,%,3600,%,60,/,'
                'FLOOR',
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
            'CDEF:system_on=PREV(system_on_un),1,EQ,system_on_un,POP,TIME,'
                'window_last,EQ,*,1,system_on_un,IF',
            'VDEF:new_average_on=system_on,AVERAGE',
            'VDEF:total_uptime_secs=system_on_un,TOTAL',
            'CDEF:total_uptime_days=uptime_sec_max,POP,total_uptime_secs,'
                '86400,/,FLOOR',
            'CDEF:total_uptime_hours=uptime_sec_max,POP,total_uptime_secs,'
                '86400,%,3600,/,FLOOR',
            'CDEF:total_uptime_mins=uptime_sec_max,POP,total_uptime_secs,'
                '86400,%,3600,%,60,/,FLOOR',
            'VDEF:tot_uptime_days=total_uptime_days,LAST',
            'VDEF:tot_uptime_hours=total_uptime_hours,LAST',
            'VDEF:tot_uptime_mins=total_uptime_mins,LAST',
            'CDEF:temp_perc_on=uptime_sec_max,POP,total_uptime_secs,delta,/,'
                '100,*',
            'VDEF:new_perc_on=temp_perc_on,LAST',
            'COMMENT:\s',
            'COMMENT:  ',
            'AREA:current_uptime_graph#66666640',
            'LINE1:current_uptime_graph#F17742:Current\:',
            'GPRINT:curr_uptime_days:%5.0lf days',
            'GPRINT:curr_uptime_hours:%3.0lf hours',
            'GPRINT:curr_uptime_mins:%3.0lf mins',
            #'GPRINT:curr_uptime_mins:%x:strftime',
            'COMMENT:\\n',
            'COMMENT:  ',
            'LINE1:max_uptime_graph#DA1F3D:Maximum\::dashes',
            'GPRINT:max_uptime_days:%5.0lf days',
            'GPRINT:max_uptime_hours:%3.0lf hours',
            'GPRINT:max_uptime_mins:%3.0lf mins',
            #'GPRINT:max_uptime_mins:%x:strftime',
            'COMMENT:\\n',
            'COMMENT:  ',
            'HRULE:min_uptime_graph#FCE053:Minimum\::dashes',
            'GPRINT:min_uptime_days:%5.0lf days',
            'GPRINT:min_uptime_hours:%3.0lf hours',
            'GPRINT:min_uptime_mins:%3.0lf mins',
            #'GPRINT:min_uptime_mins:%x:strftime',
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
            #'GPRINT:new_perc_on:%3.2lf%% up in this time window',
            'COMMENT:\\n',
            'PRINT:new_perc_on:%lf %%',
            'PRINT:total_uptime_secs:%lf secs',
            'PRINT:new_average_on:%lf %%',
            'COMMENT:\s'
        ]

        return args


class DiskPlugin(RRDBase):

    vertical_label = "Bytes/s"

    def get_title(self):
        title = self.identifier.replace("disk-", "")
        return 'Disk I/O (%s)' % title

    def get_identifiers(self):
        from freenasUI.middleware.connector import connection as dispatcher
        sources = dispatcher.call_sync('statd.output.get_data_sources')
        ids = []
        for source in sources:
            name = source.split('.')
            if len(name) < 3:
                continue
            if not name[1].startswith('disk'):
                continue
            ident = name[1].split('-', 1)[-1]
            if ident in ids:
                continue
            if not os.path.exists('/dev/%s' % ident):
                continue
            if ident.startswith('pass') or ident.startswith('cd'):
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_identifiers)
        return ids

    def get_sources(self):
        return {
            'localhost.disk-%s.disk_octets.read' % self.identifier: {
                'verbose_name': 'Read',
            },
            'localhost.disk-%s.disk_octets.write' % self.identifier: {
                'verbose_name': 'Write',
            },
        }


class ARCSizePlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = "Size"

    def get_title(self):
        return 'ARC Size'

    def graph(self):

        cachearc = os.path.join(self.base_path, "cache_size-arc.rrd")
        cachel2 = os.path.join(self.base_path, "cache_size-L2.rrd")

        args = [
            'DEF:arc_size=%s:value:MAX' % cachearc,
            'DEF:l2arc_size=%s:value:MAX' % cachel2,
            'LINE1:arc_size#0000FF:ARC Size\l',
            'GPRINT:arc_size:LAST:Cur\: %.2lf%S',
            'GPRINT:arc_size:AVERAGE:Avg\: %.2lf%S',
            'GPRINT:arc_size:MAX:Max\: %.2lf%S',
            'GPRINT:arc_size:MIN:Min\: %.2lf%S\l',
            'LINE1:l2arc_size#FF0000:L2ARC Size\l',
            'GPRINT:l2arc_size:LAST:Cur\: %.2lf%S',
            'GPRINT:l2arc_size:AVERAGE:Avg\: %.2lf%S',
            'GPRINT:l2arc_size:MAX:Max\: %.2lf%S',
            'GPRINT:l2arc_size:MIN:Min\: %.2lf%S',
        ]

        return args


class ARCRatioPlugin(RRDBase):

    plugin = 'zfs_arc'
    vertical_label = "Hit (%)"

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
            'LINE1:arc_p#0000FF:ARC Hit',
            'GPRINT:arc_p:LAST:Cur\: %4.2lf%s',
            'GPRINT:arc_p:AVERAGE:Avg\: %4.2lf%s',
            'GPRINT:arc_p:MAX:Max\: %4.2lf%s',
            'GPRINT:arc_p:MIN:Min\: %4.2lf%s',
            'LINE1:l2arc_p#FF0000:L2ARC Hit',
            'GPRINT:l2arc_p:LAST:Cur\: %4.2lf%s',
            'GPRINT:l2arc_p:AVERAGE:Avg\: %4.2lf%s',
            'GPRINT:l2arc_p:MAX:Max\: %4.2lf%s',
            'GPRINT:l2arc_p:MIN:Min\: %4.2lf%s',
        ]

        return args
