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


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = re.search(r'^(?P<name>.+)Plugin$', name)
        if reg:
            klass.plugin = reg.group("name").lower()
            klass.base_path = os.path.join(RRD_BASE_PATH, klass.plugin)
        return klass


class RRDBase(object):

    __metaclass__ = RRDMeta

    title = None
    vertical_label = None
    imgformat = 'PNG'
    unit = 'hourly'

    def __init__(self, unit=None):
        if unit:
            self.unit = str(unit)

    def __repr__(self):
        return '<RRD:%s>' % self.plugin

    def graph(self):
        raise NotImplementedError

    def generate(self):
        time = '1%s' % (self.unit[0], )
        fh, path = tempfile.mkstemp()
        args = [
            path,
            '--imgformat', self.imgformat,
            '--vertical-label', str(self.vertical_label),
            '--title', str(self.title),
            '--lower-limit', '0',
            '--end', 'now',
            '--start', 'end-%s' % time, '-b', '1024',
        ]
        args.extend(self.graph())
        print rrdtool.graph(*args)
        return path


class CPUPlugin(RRDBase):

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
