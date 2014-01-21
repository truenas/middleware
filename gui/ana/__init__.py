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
from collections import defaultdict, OrderedDict
from decimal import Decimal as D
from subprocess import Popen, PIPE
import logging
import re

from freenasUI.freeadmin.apppool import appPool
from freenasUI.ana import rrd
from freenasUI.tools import arc_summary
from .hook import AnaHook
appPool.register(AnaHook)

log = logging.getLogger('ana.__init__')

RRD_BASE_PATH = "/var/db/collectd/rrd/localhost"

bit_values = {
    'B': 1,
    'K': 1024,
    'M': 1024000,
    'G': 1024000000,
    'T': 1024000000000,
}


def dict_hash():
    return defaultdict(dict_hash)


class DataAccessClient(object):
    """
    Data Access Library (DAL)
    This Library is to access data from various locations and data sources,
    while keeping a consistent interface for the application. This library is
    intended to be where the heavy lifting in data access and data manipulation
    happens, so the application logic can stay fairly simple. If there is data
    or location specific manipulation needed for the application, it should be
    done here NOT in the application.
    """

    def __init__(self):
        self._plugins = {}
        self._load_targets()

    def _load_targets(self):
        self._plugins.clear()
        for name, plugin in rrd.name2plugin.items():
            self._plugins[name] = plugin(RRD_BASE_PATH)

    def get_plugin(self, name):
        return self._plugins.get(name)

    def _cmd(self, cmd, split='\n'):
        """
        Run commands at the command line of the machine.
        """
        p = Popen(
            cmd,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            shell=True,
            close_fds=True
        )
        output_list = p.communicate()[0].split(split)
        output_list.pop()

        return output_list

    def get_zfs_info(self, tank):

        tank = tank.replace('_', '/')

        item_get = [
            'name',
            'quota',
            'usedbysnapshots',
            'refcompressratio',
            'refreservation',
            'referenced',
            'reservation',
            'creation',
            'used',
            'available',
            'type',
            'volsize',
            'usedbydataset',
            'usedbychildren'
        ]

        item_get_str = ','.join(item_get)

        output_list = self._cmd('/sbin/zfs get -H -o value %s %s' % (
            item_get_str,
            tank)
        )

        val_dict = {}
        for i in output_list:
            val_dict[item_get[output_list.index(i)]] = i

        return val_dict

    def get_zfs_list(self, volume):

        header = [
            'NAME',
            'USED',
            'AVAIL',
            'REFER',
            'MOUNTPOINT'
        ]

        #output = run('zfs list -H')
        #tank_list = output.split('\r\n')
        tank_list = self._cmd('/sbin/zfs list -Hr %s' % volume)

        val_dict = dict_hash()

        for i in tank_list:
            t_list = i.split('\t')
            for t in t_list:
                val_dict[t_list[0]][header[t_list.index(t)]] = t

            val_dict[t_list[0]]['token'] = (
                val_dict[t_list[0]]['NAME'].replace('/', '_')
            )

        return val_dict

    def get_zfs_zpool_list(self, volume):

        header = [
            'NAME',
            'SIZE',
            'ALLOC',
            'FREE',
            'CAP',
            'DEDUP',
            'HEALTH',
            'ALTROOT'
        ]

        zpool_list = self._cmd('/sbin/zpool list -H %s' % volume, '\t')

        val_dict = {}
        for i in zpool_list:
            val_dict[header[zpool_list.index(i)]] = i

        return val_dict

    def get_data(self, target_type, **kwargs):
        plugin = rrd.name2plugin.get(target_type)
        if plugin is None:
            log.warn("Reporting plugin %s not found", target_type)
            return []
        return plugin(RRD_BASE_PATH).fetch(**kwargs)

    def get_real_time_val(self, name, data_list):
        plugin = self.get_plugin(name)
        if plugin is None:
            log.warn("Reporting plugin %s not found", name)
            return {}

        if not data_list:
            return {}

        return plugin.get_last_value(data_list)

    def get_arc_summ(self):
        kstat = self._get_Kstat()

        output = {
            'arc_efficiency': arc_summary.get_arc_efficiency(kstat),
            'arc_summary': arc_summary.get_arc_summary(kstat),
            'dmu_summary': arc_summary.get_dmu_summary(kstat),
            'l2_arc_summary': arc_summary.get_l2arc_summary(kstat),
            'system_memory': arc_summary.get_system_memory(kstat),
            'vdev_summary': arc_summary.get_vdev_summary(kstat),
            'sysctl_summary': self.systl_summary(),
        }

        return output

    def get_dev(self, target_type):
        """
        This function gets a list of devices (targets) that have been saved in
        the database
        """
        tg_dict = OrderedDict()
        sub_type = []

        plugin = rrd.name2plugin.get(target_type)
        if plugin is None:
            return {}, []
        plugin = plugin(RRD_BASE_PATH)
        idents = plugin.get_identifiers() or []
        for ident in idents:
            if '-' in ident:
                dev = ident.split('-', 1)[1]
            else:
                dev = ident
            tg_dict[dev] = dev
            for path, name in plugin.get_types(identifier=ident):
                sub_type.append(name)

        if not idents:
            tg_dict[plugin.plugin] = plugin.plugin
            for path, name in plugin.get_types():
                sub_type.append(name)

        return tg_dict, list(set(sub_type))

    def _get_Kstat(self, Kstats=None, desc=None):
        """
        This member function is the entry point for Kstats used to get the
        information needed for Arc Summary
        """
        kstat_pobj = re.compile("^([^:]+):\s+(.+)\s*$", flags=re.M)

        if not Kstats:
            Kstats = [
                "hw.pagesize",
                "hw.physmem",
                "kern.maxusers",
                "vm.kmem_map_free",
                "vm.kmem_map_size",
                "vm.kmem_size",
                "vm.kmem_size_max",
                "vm.kmem_size_min",
                "vm.kmem_size_scale",
                "vm.stats",
                "vm.swap_total",
                "vm.swap_reserved",
                "kstat.zfs",
                "vfs.zfs"
            ]

        sysctls = " ".join(str(x) for x in Kstats)

        if desc:
            kstat_pull = self._cmd('/sbin/sysctl -qde ' + sysctls)
        else:
            kstat_pull = self._cmd('/sbin/sysctl -q ' + sysctls)

        #kstat_pull = output.split('\r\n')
        #if output.return_code != 0:
        #    sys.exit(1)

        Kstat = {}
        if desc:
            for kstat in kstat_pull:
                if not kstat:
                    continue
                kstat = kstat.strip()
                name, description = kstat.split('=')[:2]
                name = name.strip()
                description = description.strip()
                if not description:
                    description = "Description unavailable"
                Kstat[name] = description
        else:
            for kstat in kstat_pull:
                kstat = kstat.strip()
                mobj = kstat_pobj.match(kstat)
                if mobj:
                    key = mobj.group(1).strip()
                    val = mobj.group(2).strip()
                    Kstat[key] = D(val)
        return Kstat

    def systl_summary(self):
        output = dict_hash()
        Tunable = [
            "kern.maxusers",
            "vm.kmem_size",
            "vm.kmem_size_scale",
            "vm.kmem_size_min",
            "vm.kmem_size_max",
            "vfs.zfs"
        ]

        Kstat_desc = self._get_Kstat(Tunable, True)
        Kstat = self._get_Kstat(Tunable)

        for key, value in Kstat.iteritems():
            output['zfs_tunable_sysctl'][key] = {
                'desc': Kstat_desc[key].capitalize(),
                'num': value,
            }

        return output
