import itertools
import json
import psutil
import subprocess
import time

from middlewared.event import EventSource
from middlewared.utils import osc

if osc.IS_FREEBSD:
    import sysctl
    import netif


class RealtimeEventSource(EventSource):

    """
    Retrieve real time statistics for CPU, network,
    virtual memory and zfs arc.
    """

    @staticmethod
    def get_cpu_usages(cp_diff):
        cp_total = sum(cp_diff)
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
        data['usage'] = ((cp_total - cp_diff[idle]) / cp_total) * 100
        return data

    def run(self):

        cp_time_last = None
        cp_times_last = None
        last_interface_stats = {}

        while not self._cancel.is_set():
            data = {}

            # Virtual memory use
            data['virtual_memory'] = psutil.virtual_memory()._asdict()

            # ZFS ARC Size (raw value is in Bytes)
            data['zfs'] = {}
            if osc.IS_FREEBSD:
                data['zfs']['arc_size'] = sysctl.filter('kstat.zfs.misc.arcstats.size')[0].value
            elif osc.IS_LINUX:
                with open('/proc/spl/kstat/zfs/arcstats') as f:
                    rv = f.read()
                    for line in rv.split('\n'):
                        if line.startswith('size'):
                            data['zfs']['arc_size'] = int(line.strip().split()[-1])

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
            elif osc.IS_LINUX:
                cp = subprocess.run(['sensors', '-j'], capture_output=True, text=True)
                try:
                    sensors = json.loads(cp.stdout)
                except json.decoder.JSONDecodeError:
                    pass
                except Exception:
                    self.middleware.logger.error('Failed to read sensors output', exc_info=True)
                else:
                    for chip, value in sensors.items():
                        for name, temps in value.items():
                            if not name.startswith('Core '):
                                continue
                            core = name[5:].strip()
                            if not core.isdigit():
                                continue
                            core = int(core)
                            for temp, value in temps.items():
                                if 'input' in temp:
                                    data['cpu']['temperature'][core] = 2732 + int(value * 10)
                                    break

            if osc.IS_FREEBSD:
                # Interface related statistics
                data['interfaces'] = {}
                retrieve_stat_keys = ['received_bytes', 'sent_bytes']
                for iface in netif.list_interfaces().values():
                    for addr in filter(lambda addr: addr.af.name.lower() == 'link', iface.addresses):
                        addr_data = addr.__getstate__(stats=True)
                        stats_time = time.time()
                        data['interfaces'][iface.name] = {}
                        for k in retrieve_stat_keys:
                            traffic_stats = addr_data['stats'][k]
                            if last_interface_stats.get(iface.name):
                                traffic_stats = traffic_stats - last_interface_stats[iface.name][k]
                                traffic_stats = int(
                                    traffic_stats / (time.time() - last_interface_stats[iface.name]['stats_time'])
                                )
                            details_dict = {
                                k: addr_data['stats'][k],
                                f'{k}_rate': traffic_stats,
                            }
                            data['interfaces'][iface.name].update(details_dict)
                        last_interface_stats[iface.name] = {**data['interfaces'][iface.name], 'stats_time': stats_time}
            self.send_event('ADDED', fields=data)
            time.sleep(2)


def setup(middleware):
    middleware.register_event_source('reporting.realtime', RealtimeEventSource)
