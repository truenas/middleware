# Copyright 2010 iXsystems, Inc.
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
from django.conf.urls import url

from freenasUI.freeadmin.apppool import appPool
from .hook import ReportingHook
from .views import index, generic_graphs, generate

appPool.register(ReportingHook)

urlpatterns = [
    url(r'^$', index, name="reporting_index"),
    url(r'^cpu/$', generic_graphs, {'names': ['cpu', 'load', 'cputemp']}, name="reporting_cpu"),
    url(r'^disk/$', generic_graphs, {'names': ['disk', 'diskgeombusy', 'diskgeomlatency', 'diskgeomopsrwd', 'diskgeomqueue', 'disktemp']}, name="reporting_disk"),
    url(r'^memory/$', generic_graphs, {'names': ['memory', 'swap']}, name="reporting_memory"),
    url(r'^network/$', generic_graphs, {'names': ['interface']}, name="reporting_network"),
    url(r'^nfs/$', generic_graphs, {'names': ['nfsstat']}, name="reporting_nfs_stats"),
    url(r'^partition/$', generic_graphs, {'names': ['df']}, name="reporting_partition"),
    url(r'^system/$', generic_graphs, {'names': ['processes', 'uptime']}, name="reporting_system"),
    url(r'^target/$', generic_graphs, {'names': ['ctl']}, name="reporting_target"),
    url(r'^ups/$', generic_graphs, {'names': ['upsbatterycharge', 'upsremainingbattery']}, name="reporting_ups_stats"),
    url(r'^zfs/$', generic_graphs, {'names': ['arcsize', 'arcratio', 'arcresult']}, name="reporting_zfs"),
    url(r'^generate/$', generate, name="reporting_generate"),
]
