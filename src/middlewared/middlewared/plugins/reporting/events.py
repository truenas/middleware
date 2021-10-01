import itertools
import psutil
import re
import struct
import time

import sysctl
import netif
from middlewared.event import EventSource
from middlewared.plugins.reporting.iostat import DiskStats


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
        data = {}
        cp_total = sum(cp_diff) or 1
        data['user'] = cp_diff[0] / cp_total * 100
        data['nice'] = cp_diff[1] / cp_total * 100
        data['system'] = cp_diff[2] / cp_total * 100
        data['interrupt'] = cp_diff[3] / cp_total * 100
        data['idle'] = cp_diff[4] / cp_total * 100

        # Usage is the sum of all but idle
        if sum(cp_diff):
            idle = 4
            data['usage'] = ((cp_total - cp_diff[idle]) / cp_total) * 100
        else:
            data['usage'] = 0
        return data

    def get_memory_info(self, arc_size):
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
        swap = {"used": sswap.used, "total": sswap.total}

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
        last_interface_speeds = {'time': time.monotonic(), 'speeds': self.get_interface_speeds()}
        last_disk_stats = {}

        while not self._cancel.is_set():
            data = {}

            # ZFS ARC Size (raw value is in Bytes)
            hits = 0
            misses = 0
            data['zfs'] = {}
            hits = sysctl.filter('kstat.zfs.misc.arcstats.hits')[0].value
            misses = sysctl.filter('kstat.zfs.misc.arcstats.misses')[0].value
            data['zfs']['arc_max_size'] = sysctl.filter('kstat.zfs.misc.arcstats.c_max')[0].value
            data['zfs']['arc_size'] = sysctl.filter('kstat.zfs.misc.arcstats.size')[0].value
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
            num_times = 5
            cp_times = sysctl.filter('kern.cp_times')[0].value  # cp_times has values for all cores
            cp_time = sysctl.filter('kern.cp_time')[0].value  # cp_time is the sum of all cores
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
            for i in itertools.count():
                v = sysctl.filter(f'dev.cpu.{i}.temperature')
                if not v:
                    break
                data['cpu']['temperature'][i] = v[0].value
            data['cpu']['temperature_celsius'] = {k: (v - 2732) / 10 for k, v in data['cpu']['temperature'].items()}

            # Interface related statistics
            if last_interface_speeds['time'] < time.monotonic() - self.INTERFACE_SPEEDS_CACHE_INTERLVAL:
                last_interface_speeds.update({'time': time.monotonic(), 'speeds': self.get_interface_speeds()})

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

            # Disk IO stats
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
