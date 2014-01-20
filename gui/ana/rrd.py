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
from calendar import timegm
from collections import defaultdict
import datetime
import logging
import os
import re

import rrdtool

log = logging.getLogger('ana.rrd')

name2plugin = dict()


def dict_hash():
    return defaultdict(dict_hash)


class RRDMeta(type):

    def __new__(cls, name, bases, dct):
        klass = type.__new__(cls, name, bases, dct)
        reg = re.search(r'^(?P<name>.+)Plugin$', name)
        if reg and not hasattr(klass, 'plugin'):
            klass.plugin = reg.group("name").lower()
            name2plugin[klass.plugin] = klass
        elif hasattr(klass, 'plugin'):
            name2plugin[klass.plugin] = klass
        elif name != 'RRDBase':
            raise ValueError("Could not determine plugin name %s" % str(name))
        return klass


class RRDBase(object):

    __metaclass__ = RRDMeta

    base_path = None
    identifier = None
    title = None

    def __init__(self, base_path, identifier=None):
        if identifier is not None:
            self.identifier = str(identifier)
        self.base_path = base_path

        self._identifiers = self.get_identifiers()
        self._types = {}
        if self._identifiers is not None:
            for ident in self._identifiers:
                self._types[ident] = self.get_types(identifier=ident)
        else:
            self._types[self._identifiers] = self.get_types()

    def get_path(self):
        return os.path.join(self.base_path, self.plugin)

    def __repr__(self):
        return '<RRD:%s>' % self.plugin

    def get_identifiers(self):
        ids = []
        for _file in os.listdir(self.base_path):
            if not _file.startswith(self.plugin + "-") or _file == self.plugin:
                continue
            ids.append(_file.split("-", 1)[1])
        if not ids:
            return None
        else:
            ids.sort()
        return ids

    def get_types(self, identifier=None, name=None):
        if identifier is None:
            identifier = self.plugin
        else:
            identifier = "%s-%s" % (self.plugin, identifier)
        path = os.path.join(self.base_path, identifier)
        types = []
        if not os.path.exists(path):
            return types
        for _file in os.listdir(path):
            if not _file.endswith('.rrd'):
                continue
            if name and "%s.rrd" % name != _file:
                continue
            full_path = os.path.join(path, _file)
            tname = _file.replace('.rrd', '')
            types.append((full_path, tname))
        return types

    def fetch(
        self,
        identifier=None,
        target_sub_type=None,
        data_type="AVERAGE",
        data_range="hrs",
        t_range=10,
        combined=False,
        **kwargs
    ):
        """
        Fetch rrd data
        """

        end_tmp = datetime.datetime.utcnow()
        end = int(timegm(end_tmp.timetuple()))

        if data_range == "hrs":
            start_tmp = end_tmp - datetime.timedelta(hours=t_range)
        elif data_range == "day":
            start_tmp = end_tmp - datetime.timedelta(days=t_range)
        elif data_range == "min":
            start_tmp = end_tmp - datetime.timedelta(minutes=t_range)
        else:
            raise ValueError(data_range)

        first = int(timegm(start_tmp.timetuple()))

        target_dict = dict_hash()

        if combined:
            identifiers = self._identifiers
        if not combined or identifiers is None:
            identifiers = [identifier]

        for identifier in identifiers:
            base = identifier
            if base is None:
                base = self.plugin
            for path, _type in self._types.get(identifier, []):
                if target_sub_type and target_sub_type != _type:
                    continue

                info, ds_rrd, data = rrdtool.fetch(
                    str(path),
                    data_type,
                    "--start", str(first),
                    "--end", str(end),
                )

                f_start = info[0]
                #f_end = info[1]
                f_step = info[2]
                f_time = f_start
                for i in data:
                    f_time = f_time + f_step
                    i_val = {}
                    for ds in ds_rrd:
                        if i[ds_rrd.index(ds)] is not None:
                            i_val[ds] = i[ds_rrd.index(ds)]
                        else:
                            i_val[ds] = 0.0

                    if i_val:
                        if combined:
                            target_dict[f_time][base][_type] = i_val
                        else:
                            target_dict[f_time][_type] = i_val

        return self.pack_output(target_dict, combined=combined)

    def pack_output(self, target_dict, combined=False):
        """
        This member function packs the output in to the format needed for the
        charts to render
        """
        data_dict = defaultdict(list)
        out_put = []
        for k, v in target_dict.iteritems():
            for k1, v1 in v.iteritems():
                for k2, v2 in v1.iteritems():
                    if 'cpu' in k2:
                        if 'idle' not in k2:
                            data_dict[k1 + '-' + k2[4:]].append(
                                [int(str(k)[:10] + '000'), v2['value']]
                            )
                    else:
                        data_dict[str(k1) + '-' + k2].append(
                            [int(str(k)[:10] + '000'), v2]
                        )

        for key in data_dict.iterkeys():
            data_dict[key].sort()

        for key, val in data_dict.iteritems():
            key = self._remove_value_str(key)
            out_put.append({
                'name': key,
                'data': val,
            })

        return out_put

    def get_last_value(self, data_list):
        val_dict = {}

        for val in data_list:
            # We get the forth to last value, because RRD returns zeros for
            # the last few values in the data store
            tmp = val['data'][-4]

            target = self._remove_value_str(val['name'])
            val_dict[target] = long(tmp[1])
        return val_dict

    def _remove_value_str(self, target):
        return target.replace("-value", "")


class CPUPlugin(RRDBase):

    def pack_output(self, target_dict, combined=False):
        """
        This member function will take all the CPU parts and give back a
        single series of the total, with out CPU Idle
        """
        if not combined:
            return super(CPUPlugin, self).pack_output(
                target_dict,
                combined=combined)

        for k, v in target_dict.iteritems():
            for k1, v1 in v.iteritems():
                total_val = 0.0
                for k2, v2 in v1.iteritems():
                    total_val += v2['value']

                if total_val < 100:
                    total_val = 100

                for y in v1.iterkeys():
                    if v1[y]:
                        target_dict[k][k1][y]['value'] = (
                            v1[y]['value'] / total_val * 100
                        )

        data_dict = defaultdict(list)
        out_put = []
        for k, v in target_dict.iteritems():
            for k1, v1 in v.iteritems():
                if 'cpu-idle' in target_dict[k][k1]:
                    if target_dict[k][k1]['cpu-idle']['value'] > 0.0:
                        cpu_val = 100 - target_dict[k][k1]['cpu-idle']['value']
                    else:
                        cpu_val = target_dict[k][k1]['cpu-idle']['value']

                    data_dict[k1].append([int(str(k)[:10] + '000'), cpu_val])

        for key in data_dict.iterkeys():
            data_dict[key].sort()

        for key, val in data_dict.iteritems():
            key = self._remove_value_str(key)
            out_put.append({
                'name': key,
                'data': val,
                'tooltip': {'yDecimals': 2},
            })

        return out_put

    def get_last_value(self, data_list):
        val_list = []

        for val in data_list:
            # We get the forth to last value, because RRD returns zeros for
            # the last few values in the data store
            tmp = val['data'][-4]
            val_list.append(tmp[1])

        tmp_val = 0.0
        for i in val_list:
            tmp_val += i

        if val_list:
            val_ave = tmp_val / len(val_list)
        else:
            val_ave = 0.0
        return round(val_ave, 2)


class InterfacePlugin(RRDBase):

    def get_identifiers(self):
        from freenasUI.network.models import Interfaces, VLAN
        idents = super(InterfacePlugin, self).get_identifiers()
        idents = filter(
            lambda x: (
                not re.search(r'^usbus\d+$', x) and
                not re.search(r'^pf\w+\d+$', x)
            ),
            idents
        )
        """
        Order the identifiers by hierarchy priority
        e.g. lagg before phys int, vlan over lagg before lagg,
             vlan over phys before phys
        """
        for ifa in Interfaces.objects.filter(int_interface__startswith='lagg'):
            if ifa.int_interface in idents:
                idents.remove(ifa.int_interface)
                idents.insert(0, ifa.int_interface)
        for vlan in VLAN.objects.all():
            if vlan.vlan_vint not in idents:
                continue
            if vlan.vlan_pint in idents:
                idents.remove(vlan.vlan_vint)
                idents.insert(
                    idents.index(vlan.vlan_pint),
                    vlan.vlan_vint,
                )
        return idents


class MemoryPlugin(RRDBase):
    pass


class SwapPlugin(RRDBase):
    pass


class DFPlugin(RRDBase):
    pass


class UptimePlugin(RRDBase):
    pass


class ZFS_ARCPlugin(RRDBase):
    pass


class DiskPlugin(RRDBase):

    @staticmethod
    def _diskcmp(a, b):
        rega = re.search(r'^([a-z]+)(\d+)$', a)
        regb = re.search(r'^([a-z]+)(\d+)$', b)
        return cmp(
            (rega.group(1), int(rega.group(2))),
            (regb.group(1), int(regb.group(2))),
        )


    def get_identifiers(self):
        idents = super(DiskPlugin, self).get_identifiers()
        if not idents:
            return []
        idents = filter(lambda x: re.search(r'^a?da\d+$', x), idents)
        idents.sort(DiskPlugin._diskcmp)
        return idents

