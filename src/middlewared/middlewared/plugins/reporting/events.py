import itertools
import json
import psutil
import re
import struct
import subprocess
import time

import humanfriendly

from middlewared.event import EventSource
from middlewared.plugins.reporting.iostat import DiskStats
from middlewared.utils import osc

if osc.IS_FREEBSD:
    import sysctl
    import netif


MEGABIT = 131072
RE_BASE = re.compile(r'([0-9]+)base')
RE_MBS = re.compile(r'([0-9]+)Mb/s')


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """

    INTERFACE_SPEEDS_CACHE_INTERLVAL = 300

    disk_stats = None

    @staticmethod
    def get_cpu_usages(cp_diff):
        cp_total = sum(cp_diff) or 1
        data = {}
        data['user'] = cp_diff[0] / cp_total * 100
        data['nice'] = cp_diff[1] / cp_total * 100
        data['system'] = cp_diff[2] / cp_total * 100
        if osc.IS_FREEBSD:
            idle = 4
            data['interrupt'] = cp_diff[3] / cp_total * 100
            data['idle'] = cp_diff[4] / cp_total * 100
        elif osc.IS_LINUX:
            idle = 3
            data['idle'] = cp_diff[3] / cp_total * 100
            data['iowait'] = cp_diff[4] / cp_total * 100
            data['irq'] = cp_diff[5] / cp_total * 100
            data['softirq'] = cp_diff[6] / cp_total * 100
            data['steal'] = cp_diff[7] / cp_total * 100
            data['guest'] = cp_diff[8] / cp_total * 100
            data['guest_nice'] = cp_diff[9] / cp_total * 100
        # Usage is the sum of all but idle
        if sum(cp_diff):
            data['usage'] = ((cp_total - cp_diff[idle]) / cp_total) * 100
        else:
            data['usage'] = 0
        return data

    def get_memory_info(self, arc_size):
        if osc.IS_FREEBSD:
            page_size = int(sysctl.filter("hw.pagesize")[0].value)
            classes = {
                k: v if isinstance(v, int) else struct.unpack("I", v)[0] * page_size
                for k, v in [
                    (k, sysctl.filter(f"vm.stats.vm.v_{k}_count")[0].value)
                    for k in ["cache", "laundry", "inactive", "active", "wire", "free"]
                ]
            }
            classes["os_reserved"] = int(sysctl.filter("hw.physmem")[0].value) - sum(classes.values())

            classes["wire"] -= arc_size
            classes["arc"] = arc_size

            extra = {}

            sswap = psutil.swap_memory()
            swap = {
                "used": sswap.used,
                "total": sswap.total,
            }
        else:
            with open("/proc/meminfo") as f:
                meminfo = {
                    s[0]: humanfriendly.parse_size(s[1], binary=True)
                    for s in [
                        line.split(":", 1)
                        for line in f.readlines()
                    ]
                }

            classes = {}
            classes["page_tables"] = meminfo["PageTables"]
            classes["swap_cache"] = meminfo["SwapCached"]
            classes["slab_cache"] = meminfo["Slab"]
            classes["cache"] = meminfo["Cached"]
            classes["buffers"] = meminfo["Buffers"]
            classes["unused"] = meminfo["MemFree"]
            classes["arc"] = arc_size
            classes["apps"] = meminfo["MemTotal"] - sum(classes.values())

            extra = {
                "inactive": meminfo["Inactive"],
                "committed": meminfo["Committed_AS"],
                "active": meminfo["Active"],
                "vmalloc_used": meminfo["VmallocUsed"],
                "mapped": meminfo["Mapped"],
            }

            swap = {
                "used": meminfo["SwapTotal"] - meminfo["SwapFree"],
                "total": meminfo["SwapTotal"],
            }

        return {
            "classes": classes,
            "extra": extra,
            "swap": swap,
        }

    def get_interface_speeds(self):
        speeds = {}

        interfaces = self.middleware.call_sync('interface.query')
        for interface in interfaces:
            if interface['state']['active_media_subtype']:
                if m := RE_BASE.match(interface['state']['active_media_subtype']):
                    speeds[interface['name']] = int(m.group(1)) * MEGABIT
                elif m := RE_MBS.match(interface['state']['active_media_subtype']):
                    speeds[interface['name']] = int(m.group(1)) * MEGABIT

        types = ['BRIDGE', 'LINK_AGGREGATION', 'VLAN']
        for interface in sorted([i for i in interfaces if i['type'] in types], key=lambda i: types.index(i['type'])):
            speed = None

            if interface['type'] == 'BRIDGE':
                member_speeds = [speeds.get(member) for member in interface['bridge_members'] if speeds.get(member)]
                if member_speeds:
                    speed = max(member_speeds)

            if interface['type'] == 'LINK_AGGREGATION':
                port_speeds = [speeds.get(port) for port in interface['lag_ports'] if speeds.get(port)]
                if port_speeds:
                    if interface['lag_protocol'] in ['LACP', 'LOADBALANCE', 'ROUNDROBIN']:
                        speed = sum(port_speeds)
                    else:
                        speed = min(port_speeds)

            if interface['type'] == 'VLAN':
                speed = speeds.get(interface['vlan_parent_interface'])

            if speed:
                speeds[interface['name']] = speed

        return speeds

    def run(self):

        cp_time_last = None
        cp_times_last = None
        last_interface_stats = {}
        last_interface_speeds = {
            'time': time.monotonic(),
            'speeds': self.get_interface_speeds(),
        }
        self.disk_stats = DiskStats()

        while not self._cancel.is_set():
            data = {}


            # ZFS ARC Size (raw value is in Bytes)
            hits = 0
            misses = 0
            data['zfs'] = {}
            if osc.IS_FREEBSD:
                hits = sysctl.filter('kstat.zfs.misc.arcstats.hits')[0].value
                misses = sysctl.filter('kstat.zfs.misc.arcstats.misses')[0].value
                data['zfs']['arc_max_size'] = sysctl.filter('kstat.zfs.misc.arcstats.c_max')[0].value
                data['zfs']['arc_size'] = sysctl.filter('kstat.zfs.misc.arcstats.size')[0].value
            elif osc.IS_LINUX:
                with open('/proc/spl/kstat/zfs/arcstats') as f:
                    for line in f.readlines()[2:]:
                        if line.strip():
                            name, type, value = line.strip().split()
                            if name == 'hits':
                                hits = int(value)
                            if name == 'misses':
                                misses = int(value)
                            if name == 'c_max':
                                data['zfs']['arc_max_size'] = int(value)
                            if name == 'size':
                                data['zfs']['arc_size'] = int(value)
            total = hits + misses
            if total > 0:
                data['zfs']['cache_hit_ratio'] = hits / total
            else:
                data['zfs']['cache_hit_ratio'] = 0

            # Virtual memory use
            data['memory'] = self.get_memory_info(data['zfs']['arc_size'])
            data['virtual_memory'] = psutil.virtual_memory()._asdict()

            data['cpu'] = {}
            # Get CPU usage %
            if osc.IS_FREEBSD:
                num_times = 5
                # cp_times has values for all cores
                cp_times = sysctl.filter('kern.cp_times')[0].value
                # cp_time is the sum of all cores
                cp_time = sysctl.filter('kern.cp_time')[0].value
            elif osc.IS_LINUX:
                num_times = 10
                with open('/proc/stat') as f:
                    stat = f.read()
                cp_times = []
                cp_time = []
                for line in stat.split('\n'):
                    if line.startswith('cpu'):
                        line_ints = [int(i) for i in line[5:].strip().split()]
                        # cpu has a sum of all cpus
                        if line[3] == ' ':
                            cp_time = line_ints
                        # cpuX is for each core
                        else:
                            cp_times += line_ints
                    else:
                        break
            else:
                cp_time = cp_times = None

            if cp_time and cp_times and cp_times_last:
                # Get the difference of times between the last check and the current one
                # cp_time has a list with user, nice, system, interrupt and idle
                cp_diff = list(map(lambda x: x[0] - x[1], zip(cp_times, cp_times_last)))
                cp_nums = int(len(cp_times) / num_times)
                for i in range(cp_nums):
                    data['cpu'][i] = self.get_cpu_usages(cp_diff[i * num_times:i * num_times + num_times])

                cp_diff = list(map(lambda x: x[0] - x[1], zip(cp_time, cp_time_last)))
                data['cpu']['average'] = self.get_cpu_usages(cp_diff)

            cp_time_last = cp_time
            cp_times_last = cp_times

            # CPU temperature
            data['cpu']['temperature'] = {}
            if osc.IS_FREEBSD:
                for i in itertools.count():
                    v = sysctl.filter(f'dev.cpu.{i}.temperature')
                    if not v:
                        break
                    data['cpu']['temperature'][i] = v[0].value
            data['cpu']['temperature_celsius'] = {k: (v - 2732) / 10 for k, v in data['cpu']['temperature'].items()}

            # Interface related statistics
            if last_interface_speeds['time'] < time.monotonic() - self.INTERFACE_SPEEDS_CACHE_INTERLVAL:
                last_interface_speeds.update({
                    'time': time.monotonic(),
                    'speeds': self.get_interface_speeds(),
                })
            if osc.IS_FREEBSD:
                # Interface related statistics
                data['interfaces'] = {}
                retrieve_stat_keys = ['received_bytes', 'sent_bytes']
                for iface in netif.list_interfaces().values():
                    for addr in filter(lambda addr: addr.af.name.lower() == 'link', iface.addresses):
                        addr_data = addr.__getstate__(stats=True)
                        stats_time = time.time()
                        data['interfaces'][iface.name] = {
                            'speed': last_interface_speeds['speeds'].get(iface.name),
                        }
                        for k in retrieve_stat_keys:
                            traffic_stats = 0
                            if last_interface_stats.get(iface.name):
                                traffic_stats = addr_data['stats'][k] - last_interface_stats[iface.name][k]
                                traffic_stats = int(
                                    traffic_stats / (time.time() - last_interface_stats[iface.name]['stats_time'])
                                )
                            details_dict = {
                                k: addr_data['stats'][k],
                                f'{k}_rate': traffic_stats,
                            }
                            data['interfaces'][iface.name].update(details_dict)
                        last_interface_stats[iface.name] = {**data['interfaces'][iface.name], 'stats_time': stats_time}
            data['disks'] = self.disk_stats.read()

            self.send_event('ADDED', fields=data)
            time.sleep(2)

    def on_finish(self):
        if self.disk_stats != None:
            self.disk_stats.stop()


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource)
