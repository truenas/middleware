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
from django.conf.urls import patterns, url

urlpatterns = patterns('ana.views',
    url(r'^$', 'index', name='ana_index'),
    url(r'^dashboard/$', 'dashboard', name='ana_dashboard'),
    url(r'^cpus/$', 'cpus', name='ana_cpus'),
    url(r'^interface/$', 'interface', name='ana_interface'),
    url(r'^df/$', 'partition', name='ana_partition'),
    url(r'^disk/$', 'disk', name='ana_report_disk'),
    url(r'^memory/$', 'memory', name='ana_memory'),

    url(r'^zfs_details/$', 'zfs_details', name='ana_zfs_details'),

    url(r'^tg/memory/$', 'tg_memory', name='ana_tg_memory'),
    url(r'^tg/memory/(?P<data_range>\w+)/(?P<t_range>\d+)/$', 'tg_memory', name='ana_tg_memory'),

    url(r'^tg/cpu/$', 'tg_cpu', name='ana_tg_cpu'),
    url(r'^tg/cpu/(?P<cpu_type>[^/]+)/(?P<data_range>\w+)/(?P<t_range>\d+)/(?P<combined>\d+)/$', 'tg_cpu', name='ana_tg_cpu'),
    #url(r'^tg/partition/$', 'tg_partition', name='tg_partition'),

    url(r'^tg/disk/$', 'tg_disk', name='ana_tg_disk'),
    url(r'^tg/disk/(?P<disk>[^/]+)/$', 'tg_disk', name='ana_tg_disk'),
    url(r'^tg/disk/(?P<disk>[^/]+)/(?P<data_type>\w+)/$', 'tg_disk', name='ana_tg_disk'),
    url(r'^tg/disk/(?P<disk>[^/]+)/(?P<data_type>\w+)/(?P<data_range>\w+)/(?P<t_range>\d+)/$', 'tg_disk', name='ana_tg_disk'),

    url(r'^tg/network/$', 'tg_network', name='ana_tg_network'),
    url(r'^tg/network/(?P<interface>\w+)/$', 'tg_network', name='ana_tg_network'),
    url(r'^tg/network/(?P<interface>\w+)/(?P<data_type>\w+)/$', 'tg_network', name='ana_tg_network'),
    url(r'^tg/network/(?P<interface>\w+)/(?P<data_type>\w+)/(?P<data_range>\w+)/(?P<t_range>\d+)/$', 'tg_network', name='ana_tg_network'),

    url(r'^tg/zfs_arc/$', 'tg_zfs_arc', name='ana_tg_zfs_arc'),
    url(r'^tg/zfs_arc/(?P<data_type>[^/]+)/$', 'tg_zfs_arc', name='ana_tg_zfs_arc'),
    url(r'^tg/zfs_arc/(?P<data_type>[^/]+)/(?P<data_range>\w+)/(?P<t_range>\d+)/$', 'tg_zfs_arc', name='ana_tg_zfs_arc'),

    url(r'^rt/cpu/$', 'rt_cpu', name='ana_rt_cpu'),
    url(r'^rt/partition/$', 'rt_partition', name='ana_rt_partition'),
    url(r'^rt/network/$', 'rt_network', name='ana_rt_network'),
    url(r'^rt/memory/$', 'rt_memory', name='ana_rt_memory'),
    url(r'^rt/storage/(?P<volume>.+?)/val/(?P<value>\w+)$', 'rt_storage_pie', name='ana_rt_storage_val'),
    url(r'^rt/storage/(?P<volume>.+?)/pie/$', 'rt_storage_pie', name='ana_rt_storage_pie'),

    url(r'^zfs/info/$', 'zfs_info', name='ana_zfs_info'),
    url(r'^zfs/info/(?P<volume>.+)/$', 'zfs_info', name='ana_zfs_info'),
    url(r'^zfs/tank/list/$', 'zfs_tank_list', name='ana_zfs_tank_list'),
    url(r'^zfs/zpool/list/$', 'zfs_zpool_list', name='ana_zfs_zpool_list'),

    url(r'^zfs/pie/(?P<volume>.+?)/$', 'zfs_info_pie', name='ana_zfs_info_pie'),
    url(r'^zfs/sum/$', 'zfs_sum', name='ana_zfs_sum'),

    url(r'^zfs/pie/(?P<tank>\w+)/$', 'zfs_info_pie', name='ana_zfs_info_pie'),
    )
