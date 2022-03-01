from collections import defaultdict
import glob
import psutil
import re
import time

import humanfriendly

from middlewared.event import EventSource
from middlewared.plugins.interface.netif import netif

from .iostat import DiskStats


MEGABIT = 131072
RE_BASE = re.compile(r'([0-9]+)base')
RE_MBS = re.compile(r'([0-9]+)Mb/s')


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """

    INTERFACE_SPEEDS_CACHE_INTERLVAL = 300
    INTERVAL = 2

    @staticmethod
    def get_cpu_usages(cp_diff):
        cp_total = sum(cp_diff) or 1
        data = {}
        data['user'] = cp_diff[0] / cp_total * 100
        data['nice'] = cp_diff[1] / cp_total * 100
        data['system'] = cp_diff[2] / cp_total * 100
        data['idle'] = cp_diff[3] / cp_total * 100
        data['iowait'] = cp_diff[4] / cp_total * 100
        data['irq'] = cp_diff[5] / cp_total * 100
        data['softirq'] = cp_diff[6] / cp_total * 100
        data['steal'] = cp_diff[7] / cp_total * 100
        data['guest'] = cp_diff[8] / cp_total * 100
        data['guest_nice'] = cp_diff[9] / cp_total * 100
        if sum(cp_diff):
            # Usage is the sum of all but idle
            idle = 3
            data['usage'] = ((cp_total - cp_diff[idle]) / cp_total) * 100
        else:
            data['usage'] = 0
        return data

    def get_memory_info(self, arc_size):
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

    def run_sync(self):

        cp_time_last = None
        cp_times_last = None
        last_interface_stats = {}
        last_interface_speeds = {'time': time.monotonic(), 'speeds': self.get_interface_speeds()}
        last_disk_stats = {}

        while not self._cancel_sync.is_set():
            data = {}

            # ZFS ARC Size (raw value is in Bytes)
            hits = 0
            misses = 0
            data['zfs'] = {}
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

            # Get CPU usage %
            data['cpu'] = {}
            num_times = 10
            with open('/proc/stat') as f:
                stat = f.read()
            cp_times = []
            cp_time = []
            for line in stat.split('\n'):
                bits = line.split()
                if bits[0].startswith('cpu'):
                    line_ints = [int(i) for i in bits[1:]]
                    # cpu has a sum of all cpus
                    if bits[0] == 'cpu':
                        cp_time = line_ints
                    # cpuX is for each core
                    else:
                        cp_times += line_ints
                else:
                    break

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
            data['cpu']['temperature_celsius'] = self.middleware.call_sync('reporting.cpu_temperatures')
            data['cpu']['temperature'] = {k: 2732 + int(v * 10) for k, v in data['cpu']['temperature_celsius'].items()}

            # Interface related statistics
            if last_interface_speeds['time'] < time.monotonic() - self.INTERFACE_SPEEDS_CACHE_INTERLVAL:
                last_interface_speeds.update({
                    'time': time.monotonic(),
                    'speeds': self.get_interface_speeds(),
                })
            data['interfaces'] = defaultdict(dict)
            retrieve_stat = {'rx_bytes': 'received_bytes', 'tx_bytes': 'sent_bytes'}
            stats_time = time.time()
            for i in glob.glob('/sys/class/net/*/statistics'):
                iface_name = i.replace('/sys/class/net/', '').split('/')[0]
                if iface_name.startswith(netif.INTERNAL_INTERFACES):
                    continue

                data['interfaces'][iface_name]['speed'] = last_interface_speeds['speeds'].get(iface_name)
                for stat, name in retrieve_stat.items():
                    with open(f'{i}/{stat}', 'r') as f:
                        value = int(f.read())
                    data['interfaces'][iface_name][name] = value
                    traffic_stats = None
                    if (
                        last_interface_stats.get(iface_name) and
                        name in last_interface_stats[iface_name]
                    ):
                        traffic_stats = value - last_interface_stats[iface_name][name]
                        traffic_stats = int(
                            traffic_stats / (
                                stats_time - last_interface_stats[iface_name]['stats_time']
                            )
                        )
                    data['interfaces'][iface_name][f'{retrieve_stat[stat]}_rate'] = traffic_stats
                last_interface_stats[iface_name] = {
                    **data['interfaces'][iface_name],
                    'stats_time': stats_time,
                }

            # Disk IO Stats
            if not last_disk_stats:
                # means this is the first time disk stats are being gathered so
                # get the results but don't set anything yet since we need to
                # calculate the difference between the iterations
                last_disk_stats, new = DiskStats(self.INTERVAL, last_disk_stats).read()
            else:
                last_disk_stats, data['disks'] = DiskStats(self.INTERVAL, last_disk_stats).read()

            self.send_event('ADDED', fields=data)
            time.sleep(self.INTERVAL)


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource)
