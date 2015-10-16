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

    identifier = None
    title = None
    vertical_label = None
    unit = 'hourly'
    step = 0
    sources = {}

    def __init__(self, identifier=None, unit=None, step=None):
        if identifier is not None:
            self.identifier = str(identifier)
        if unit is not None:
            self.unit = str(unit)
        if step is not None:
            self.step = int(step)

    def __repr__(self):
        return '<RRD:%s>' % self.plugin

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

    def get_title(self):
        title = self.identifier.replace("mnt-", "")
        return 'Diskspace (%s)' % title

    def get_identifiers(self):
        from freenasUI.middleware.connector import connection as dispatcher
        sources = dispatcher.call_sync('statd.output.get_data_sources')
        ids = []
        for source in sources:
            name = source.split('.')
            if len(name) < 3:
                continue
            if not name[1].startswith('df-'):
                continue
            ident = name[1].split('-', 1)[-1]
            if not ident.startswith('mnt') or ident == 'mnt':
                continue
            if ident in ids:
                continue
            ids.append(ident)

        ids.sort(key=RRDBase._sort_identifiers)
        return ids

    def get_sources(self):
        return {
            'localhost.df-%s.df_complex-free.value' % self.identifier: {
                'verbose_name': 'Free',
            },
            'localhost.df-%s.df_complex-used.value' % self.identifier: {
                'verbose_name': 'Used',
            },
        }


class UptimePlugin(RRDBase):

    title = "Uptime"
    vertical_label = "Time"
    sources = {
        'localhost.uptime.uptime.value': {
            'verbose_name': 'Uptime',
        },
    }


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

    title = 'ARC Size'
    plugin = 'zfs_arc'
    vertical_label = "Size"
    sources = {
        'localhost.zfs_arc.cache_size-arc.value': {
            'verbose_name': 'ARC Size',
        },
        'localhost.zfs_arc.cache_size-L2.value': {
            'verbose_name': 'L2ARC Size',
        },
    }


class ARCRatioPlugin(RRDBase):

    title = 'ARC Hit Ratio'
    plugin = 'zfs_arc'
    vertical_label = "Hit (%)"
    sources = {
        'localhost.zfs_arc.cache_ratio-arc.value': {
            'verbose_name': 'ARC Hit',
        },
        'localhost.zfs_arc.cache_ratio-L2.value': {
            'verbose_name': 'L2ARC Hit',
        },
    }
