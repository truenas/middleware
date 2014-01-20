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
from collections import OrderedDict
from decimal import Decimal
import logging
import re
import struct
import subprocess
import time

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import simplejson

from freenasUI.ana import (
    DataAccessClient, dict_hash, bit_values
)
from freenasUI.common import humanize_number_si
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume

log = logging.getLogger('ana.views')
data_client = DataAccessClient()
LAST_CP_TIMES = None
LAST_NETWORK_METER = None


def index(request, template_name='ana/index.html'):
    return render(request, template_name)


def cpus(request, template_name='ana/cpus.html'):
    tg_str = []

    tg_dict, sub_types = data_client.get_dev('cpu')
    data_list = data_client.get_data(target_type='cpu', combined=True)
    rt_val = data_client.get_real_time_val('cpu', data_list)

    for k in tg_dict.iterkeys():
        tg_str.append(k)

    tg_str = ','.join(tg_str)

    data = {
        'target_dict': tg_dict,
        'sub_types': sub_types,
        'rt_val': rt_val,
        'target_str': tg_str,
    }
    return render(request, template_name, data)


def interface(request, template_name='ana/interface.html'):

    tg_str = []

    tg_dict, sub_types = data_client.get_dev('interface')
    sub_types_str = ",".join(sub_types)

    for k in tg_dict.iterkeys():
        tg_str.append(k)

    tg_str = ','.join(tg_str)

    data = {
        'target_dict': tg_dict,
        'sub_types_str': sub_types_str,
        'sub_types': sub_types,
        'target_str': tg_str,
    }
    return render(request, template_name, data)


def disk(request, template_name='ana/disk.html'):

    tg_str = []

    tg_dict, sub_types = data_client.get_dev('disk')
    sub_types_str = ",".join(sub_types)

    for k in tg_dict.iterkeys():
        tg_str.append(k)

    tg_str = ','.join(tg_str)

    data = {
        'target_dict': tg_dict,
        'sub_types_str': sub_types_str,
        'sub_types': sub_types,
        'target_str': tg_str,
    }
    return render(request, template_name, data)


def partition(request, template_name='ana/partition.html'):

    #tank_list = data_client.get_zfs_list()
    return render(request, template_name, {
        #'tankList': dict(tank_list),
        'volumes': Volume.objects.filter(vol_fstype='ZFS'),
        })


def dashboard(request, template_name='ana/dashboard.html'):

    arc_summ = data_client.get_arc_summ()

    return render(request, template_name, {
        'system_memory': arc_summ['system_memory'],
        'arc_efficiency': arc_summ['arc_efficiency'],
        'arc_size': arc_summ['arc_summary']['arc_sizing'],
        'volumes': Volume.objects.filter(vol_fstype='ZFS'),
    })


def zfs_details(request, template_name='ana/zfs_details.html'):

    arc_summ = data_client.get_arc_summ()

    sub_types = data_client.get_dev('zfs_arc')[1]

    return render(request, template_name, {
        'arc_summ': arc_summ,
        'zfs_tunable_sysctl': dict(arc_summ['sysctl_summary']['zfs_tunable_sysctl']),
        'sub_types': sub_types,
        'sub_types_str': ','.join([s[1] for s in sub_types]),
    })


def memory(request, template_name='ana/memory.html'):

    data_list = data_client.get_data(target_type='memory')
    rt_val = data_client.get_real_time_val('memory', data_list)

    output_dict = {}
    for k, v in rt_val.iteritems():
        output_dict[k.split('-')[1]] = humanize_number_si(v)

    return render(request, template_name, {
        'rt_val': output_dict,
    })


def tg_cpu(request, cpu_type='cpu', data_range='hrs', t_range=10, combined=0):
    data_list = data_client.get_data(
        target_type='cpu',
        identifier=cpu_type,
        data_range=data_range,
        t_range=int(t_range),
        combined=bool(int(combined)))
    if not data_list:
        data_list = [{}]
    return HttpResponse(simplejson.dumps(data_list),
        mimetype='application/javascript')


def tg_partition(request):
    data_list = data_client.get_data(target_type='df', combined=True)
    rt_val = data_client.get_real_time_val('memory', data_list)
    tmp_dict = dict_hash()
    categories = []

    for i in rt_val.iterkeys():
        target = i.split('-')
        t_type = target[-1]
        t_body = '-'.join(target[:-1])

        tmp_dict[t_body][t_type] = rt_val[i]

    out_put_list = []
    used = []
    free = []
    for k1, v1 in tmp_dict.iteritems():
        tmp_name = k1.split('-')
        name = ' '.join(tmp_name[-2:])
        categories.append(name)
        used.append(v1['used'])
        free.append(v1['free'])

    out_put_list.append({'name': 'used', 'data': used})
    out_put_list.append({'name': 'free', 'data': free})

    return HttpResponse(simplejson.dumps({
        'data': out_put_list,
        'categories': categories,
        }), mimetype='application/javascript')


def tg_memory(request, data_range='hrs', t_range=10):

    data_list = data_client.get_data(
        target_type='memory',
        data_range=data_range,
        t_range=int(t_range))

    return HttpResponse(simplejson.dumps(data_list),
        mimetype='application/javascript')


def tg_network(request, interface=None, data_type='', data_range='hrs',
        t_range=10):
    if not interface:
        return HttpResponse(simplejson.dumps({}),
            mimetype='application/javascript')

    if data_type:
        target_sub_type = data_type
    data_list = data_client.get_data(
        target_type='interface',
        identifier=interface,
        target_sub_type=target_sub_type,
        data_range=data_range,
        t_range=int(t_range))

    return HttpResponse(simplejson.dumps(data_list),
        mimetype='application/javascript')


def tg_zfs_arc(request, data_type='', data_range='hrs', t_range=10):

    data_list = data_client.get_data(
        target_type='zfs_arc',
        target_sub_type=data_type,
        data_range=data_range,
        t_range=int(t_range)
    )

    return HttpResponse(simplejson.dumps(data_list),
        mimetype='application/javascript')


def tg_disk(request, disk=None, data_type='', data_range='hrs', t_range=10):

    if not disk:
        return HttpResponse(simplejson.dumps({}),
            mimetype='application/javascript')

    data_list = data_client.get_data(
        target_type='disk',
        identifier=disk,
        target_sub_type=data_type,
        data_range=data_range,
        t_range=int(t_range))

    return HttpResponse(simplejson.dumps(data_list),
        mimetype='application/javascript')


def rt_cpu(request):
    """
    collectd values for CPU are not good enough for real time CPU measurements.
    That said, we need to grab aggregated avarage CPU times to calculate
    the % of cpu busy, which is done using the kern.cpu_time sysctl.

    The big issue here is that we need at least 2 measurements to get an
    "accurate" real time measure, otherwise we get an overall avarage.
    However, as we are taking measures in every HTTP request the CPU usage is
    going to be the usage between two consecutive HTTP requests.

    XXX: FIXME
    Another big issue is that the values are stored in the local thread, so
    is no guarantee that the HTTP requests are going to use the same as the
    one before.
    Also, the first request will be always the total avarage as we have only
    one measurement point.
    XXX
    """

    global LAST_CP_TIMES
    cp_times = notifier().sysctl("kern.cp_time")
    if LAST_CP_TIMES is None:
        busy = Decimal(sum(cp_times[:4]))
        total = Decimal(sum(cp_times))
        rt_val = (busy / total) * 100
    else:
        busy = Decimal(sum(cp_times[:4]))
        total = Decimal(sum(cp_times))
        busy2 = Decimal(sum(LAST_CP_TIMES[:4]))
        total2 = Decimal(sum(LAST_CP_TIMES))
        rt_val = ((busy - busy2) / (total - total2)) * 100

    LAST_CP_TIMES = cp_times

    return HttpResponse(
        simplejson.dumps(float("%.2f" % rt_val)),
        mimetype='application/javascript'
    )


def rt_partition(request):
    data_list = data_client.get_data(target_type='df', combined=True)
    rt_val = data_client.get_real_time_val('df', data_list)
    tmp_dict = dict_hash()
    free = Decimal('0.0')
    used = Decimal('0.0')
    pre = Decimal('0.0')

    for i in rt_val.iterkeys():
        target = i.split('-')
        t_type = target[-1]
        t_body = '-'.join(target[:-1])

        tmp_dict[t_body][t_type] = rt_val[i]

    for k in tmp_dict.iterkeys():
        used += Decimal(tmp_dict[k]['used'])
        free += Decimal(tmp_dict[k]['free'])

    if free:
        pre = (used / free) * 100

    return HttpResponse(simplejson.dumps(pre),
        mimetype='application/javascript')


def rt_memory(request):
    data_list = data_client.get_data(target_type='memory')
    rt_val = data_client.get_real_time_val('memory', data_list)

    if not rt_val:
        rt_val = 0

    output_dict = {}
    for k, v in rt_val.iteritems():
        output_dict[k.split('-')[1]] = v

    return HttpResponse(simplejson.dumps(output_dict),
        mimetype='application/javascript')


def rt_network(request):
    global LAST_NETWORK_METER

    proc = subprocess.Popen([
        "/usr/bin/netstat",
        "-i",  # per interface statistics
        "-f", "link",  # link protocol family
        "-b",  # display bytes
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    data = '\n'.join(proc.communicate()[0].split('\n')[1:])
    utime = time.time()

    data = re.sub(r'^(lo0|pf|plip|usbus).*?\n', '', data, flags=re.M).strip('\n')
    data = re.sub(r'[ \t]+', ' ', data)

    rx, tx = 0, 0
    for iface in data.split('\n'):
        rx += int(iface.split(' ')[7])
        tx += int(iface.split(' ')[10])

    if LAST_NETWORK_METER is None:
        LAST_NETWORK_METER = {
            'time': utime,
            'rx': rx,
            'tx': tx,
        }
        stat = {'rx': 0, 'tx': 0}
    else:
        difftime = utime - LAST_NETWORK_METER['time']
        stat = {
            'rx': float(((rx - LAST_NETWORK_METER['rx']) / difftime)),
            'tx': float(((tx - LAST_NETWORK_METER['tx']) / difftime)),
        }
        LAST_NETWORK_METER = {
            'time': utime,
            'rx': rx,
            'tx': tx,
        }

    return HttpResponse(simplejson.dumps(stat),
        mimetype='application/javascript')


def rt_storage_pie(request, volume, value=None):
    tmp_dict = {
        'used': OrderedDict(),
        'free': OrderedDict(),
    }
    #total_space = 0
    data = []
    used_total = 0
    sub_tank = Decimal('0.0')
    volume = Volume.objects.get(vol_name=volume)

    zpool_info = data_client.get_zfs_zpool_list(volume.vol_name)
    zpool_size = check_val(zpool_info['SIZE'])

    for dataset in volume.get_datasets(include_root=True).values():
        name = dataset.full_name
        tmp_dict['used'][name] = check_val(dataset.refer)
        tmp_dict['free'][name] = check_val(dataset.avail)

    for name, zvol in volume.get_zvols().items():
        tmp_dict['used'][name] = check_val(zvol.get("refer"))
        tmp_dict['free'][name] = check_val(zvol.get("avail"))
        sub_tank += check_val(zvol.get("used"))

    for k, v in tmp_dict['used'].iteritems():
        used_total += v
        data.append([k, v])

    free_space = zpool_size - used_total

    data.append(['Free', free_space])
    #tank_size = tmp_dict['free'][zpool_info['NAME']]

    series = {
        'type': 'pie',
        'name': '%s Usage' % volume.vol_name.capitalize(),
        'data': data,
        }

    """
    If we need a total percent for storage used
    """
    if value:
        pre = 100 * (used_total / zpool_size)
        return HttpResponse(simplejson.dumps(pre),
            mimetype='application/javascript')

    return HttpResponse(simplejson.dumps(series),
        mimetype='application/javascript')


def zfs_info_pie(request, volume):

    referenced, available, quota, reservation, usedbysnapshots = (0, ) * 5

    zfs_info = data_client.get_zfs_info(volume)

    if not zfs_info:
        return HttpResponse(simplejson.dumps({}),
            mimetype='application/javascript')

    if 'referenced' in zfs_info:
        referenced = check_val(zfs_info['referenced'])

    if 'available' in zfs_info:
        available = check_val(zfs_info['available'])

    # If we have a volsize we really want to us that as available space
    if 'volsize' in zfs_info:
        if zfs_info['volsize'] != '-':
            available = check_val(zfs_info['volsize'])

    if 'quota' in zfs_info:
        quota = check_val(zfs_info['quota'])

    if 'reservation' in zfs_info:
        reservation = check_val(zfs_info['reservation'])

    if 'usedbysnapshots' in zfs_info:
        usedbysnapshots = check_val(zfs_info['usedbysnapshots'])

    if reservation > referenced:
        res = reservation - referenced
    else:
        res = 0

    # Neet to ask about this one
    if quota:
        quota = quota - referenced
        available = 0

    data_tmp = {
        'Reservation': res if res > 0 else 0,
        'Quota': quota if quota > 0 else 0,
        'Used': referenced,
        'Available': available if available > 0 else 0,
        'Usedbysnapshots': usedbysnapshots,
        }

    data = []
    for k, v in data_tmp.iteritems():
        if v:
            data.append([k, v])

    series = {
        'type': 'pie',
        'name': volume.replace('_', ' ').title() + ' Usage',
        'data': data
        }

    series_data = {
        'series': series,
        'title': volume.replace('_', ' ').title() + ' Usage',
        }

    return HttpResponse(simplejson.dumps(series_data),
        mimetype='application/javascript')


def check_val(val):

    if val:
        try:
            data = Decimal(val[:-1]) * bit_values[val[-1]]
        except:
            data = 0
    else:
        data = 0

    return data


def zfs_info(request, volume):
    if not volume:
        return HttpResponse(simplejson.dumps({}),
            mimetype='application/javascript')

    zfs_info = data_client.get_zfs_info(volume)
    return HttpResponse(simplejson.dumps(zfs_info),
        mimetype='application/javascript')


def zfs_tank_list(request):
    tank_list = data_client.get_zfs_list()
    return HttpResponse(simplejson.dumps(tank_list),
        mimetype='application/javascript')


def zfs_zpool_list(request):
    zpool_list = data_client.get_zfs_zpool_list()
    return HttpResponse(simplejson.dumps(zpool_list),
        mimetype='application/javascript')


def zfs_sum(request):
    zpool_list = data_client.get_arc_summ()
    return HttpResponse(simplejson.dumps(zpool_list),
        mimetype='application/javascript')
