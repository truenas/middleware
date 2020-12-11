#!/usr/bin/env python3
from middlewared.utils import osc

from collections import defaultdict, namedtuple
import contextlib
import copy
from datetime import datetime, timedelta
from decimal import Decimal
import os
import pty
import subprocess
import threading
import time

import libzfs
import humanfriendly
import netsnmpagent
import pysnmp.hlapi  # noqa
import pysnmp.smi
if osc.IS_FREEBSD:
    import sysctl

from middlewared.client import Client


def get_Kstat():
    if osc.IS_FREEBSD:
        return get_Kstat_FreeBSD()
    else:
        return get_Kstat_Linux()


def get_Kstat_FreeBSD():
    Kstats = [
        "kstat.zfs.misc.arcstats",
        "vfs.zfs.version.spa",
    ]

    Kstat = {}
    for kstat in Kstats:
        for s in sysctl.filter(kstat):
            if isinstance(s.value, int):
                Kstat[s.name] = Decimal(s.value)
            elif isinstance(s.value, bytearray):
                Kstat[s.name] = Decimal(int.from_bytes(s.value, "little"))

    return Kstat


def get_Kstat_Linux():
    Kstat = {}

    with open("/proc/spl/kstat/zfs/arcstats") as f:
        arcstats = f.readlines()

    for line in arcstats[2:]:
        if line.strip():
            name, type, data = line.strip().split()
            Kstat[f"kstat.zfs.misc.arcstats.{name}"] = Decimal(int(data))

    Kstat["vfs.zfs.version.spa"] = Decimal(5000)

    return Kstat


def get_arc_efficiency(Kstat):
    output = {}

    if "vfs.zfs.version.spa" not in Kstat:
        return

    arc_hits = Kstat["kstat.zfs.misc.arcstats.hits"]
    arc_misses = Kstat["kstat.zfs.misc.arcstats.misses"]
    demand_data_hits = Kstat["kstat.zfs.misc.arcstats.demand_data_hits"]
    demand_data_misses = Kstat["kstat.zfs.misc.arcstats.demand_data_misses"]
    demand_metadata_hits = Kstat[
        "kstat.zfs.misc.arcstats.demand_metadata_hits"
    ]
    demand_metadata_misses = Kstat[
        "kstat.zfs.misc.arcstats.demand_metadata_misses"
    ]
    mfu_ghost_hits = Kstat["kstat.zfs.misc.arcstats.mfu_ghost_hits"]
    mfu_hits = Kstat["kstat.zfs.misc.arcstats.mfu_hits"]
    mru_ghost_hits = Kstat["kstat.zfs.misc.arcstats.mru_ghost_hits"]
    mru_hits = Kstat["kstat.zfs.misc.arcstats.mru_hits"]
    prefetch_data_hits = Kstat["kstat.zfs.misc.arcstats.prefetch_data_hits"]
    prefetch_data_misses = Kstat[
        "kstat.zfs.misc.arcstats.prefetch_data_misses"
    ]
    prefetch_metadata_hits = Kstat[
        "kstat.zfs.misc.arcstats.prefetch_metadata_hits"
    ]
    prefetch_metadata_misses = Kstat[
        "kstat.zfs.misc.arcstats.prefetch_metadata_misses"
    ]

    anon_hits = arc_hits - (
        mfu_hits + mru_hits + mfu_ghost_hits + mru_ghost_hits
    )
    arc_accesses_total = (arc_hits + arc_misses)
    demand_data_total = (demand_data_hits + demand_data_misses)
    prefetch_data_total = (prefetch_data_hits + prefetch_data_misses)
    real_hits = (mfu_hits + mru_hits)

    output["total_accesses"] = fHits(arc_accesses_total)
    output["cache_hit_ratio"] = {
        'per': fPerc(arc_hits, arc_accesses_total),
        'num': fHits(arc_hits),
    }
    output["cache_miss_ratio"] = {
        'per': fPerc(arc_misses, arc_accesses_total),
        'num': fHits(arc_misses),
    }
    output["actual_hit_ratio"] = {
        'per': fPerc(real_hits, arc_accesses_total),
        'num': fHits(real_hits),
    }
    output["data_demand_efficiency"] = {
        'per': fPerc(demand_data_hits, demand_data_total),
        'num': fHits(demand_data_total),
    }

    if prefetch_data_total > 0:
        output["data_prefetch_efficiency"] = {
            'per': fPerc(prefetch_data_hits, prefetch_data_total),
            'num': fHits(prefetch_data_total),
        }

    if anon_hits > 0:
        output["cache_hits_by_cache_list"] = {}
        output["cache_hits_by_cache_list"]["anonymously_used"] = {
            'per': fPerc(anon_hits, arc_hits),
            'num': fHits(anon_hits),
        }

    output["most_recently_used"] = {
        'per': fPerc(mru_hits, arc_hits),
        'num': fHits(mru_hits),
    }
    output["most_frequently_used"] = {
        'per': fPerc(mfu_hits, arc_hits),
        'num': fHits(mfu_hits),
    }
    output["most_recently_used_ghost"] = {
        'per': fPerc(mru_ghost_hits, arc_hits),
        'num': fHits(mru_ghost_hits),
    }
    output["most_frequently_used_ghost"] = {
        'per': fPerc(mfu_ghost_hits, arc_hits),
        'num': fHits(mfu_ghost_hits),
    }

    output["cache_hits_by_data_type"] = {}
    output["cache_hits_by_data_type"]["demand_data"] = {
        'per': fPerc(demand_data_hits, arc_hits),
        'num': fHits(demand_data_hits),
    }
    output["cache_hits_by_data_type"]["prefetch_data"] = {
        'per': fPerc(prefetch_data_hits, arc_hits),
        'num': fHits(prefetch_data_hits),
    }
    output["cache_hits_by_data_type"]["demand_metadata"] = {
        'per': fPerc(demand_metadata_hits, arc_hits),
        'num': fHits(demand_metadata_hits),
    }
    output["cache_hits_by_data_type"]["prefetch_metadata"] = {
        'per': fPerc(prefetch_metadata_hits, arc_hits),
        'num': fHits(prefetch_metadata_hits),
    }

    output["cache_misses_by_data_type"] = {}
    output["cache_misses_by_data_type"]["demand_data"] = {
        'per': fPerc(demand_data_misses, arc_misses),
        'num': fHits(demand_data_misses),
    }
    output["cache_misses_by_data_type"]["prefetch_data"] = {
        'per': fPerc(prefetch_data_misses, arc_misses),
        'num': fHits(prefetch_data_misses),
    }
    output["cache_misses_by_data_type"]["demand_metadata"] = {
        'per': fPerc(demand_metadata_misses, arc_misses),
        'num': fHits(demand_metadata_misses),
    }
    output["cache_misses_by_data_type"]["prefetch_metadata"] = {
        'per': fPerc(prefetch_metadata_misses, arc_misses),
        'num': fHits(prefetch_metadata_misses),
    }

    return output


def fHits(Hits=0, Decimal=2):
    khits = (10 ** 3)
    mhits = (10 ** 6)
    bhits = (10 ** 9)
    thits = (10 ** 12)
    qhits = (10 ** 15)
    Qhits = (10 ** 18)
    shits = (10 ** 21)
    Shits = (10 ** 24)

    if Hits >= Shits:
        return str("%0." + str(Decimal) + "f") % (Hits / Shits) + "S"
    elif Hits >= shits:
        return str("%0." + str(Decimal) + "f") % (Hits / shits) + "s"
    elif Hits >= Qhits:
        return str("%0." + str(Decimal) + "f") % (Hits / Qhits) + "Q"
    elif Hits >= qhits:
        return str("%0." + str(Decimal) + "f") % (Hits / qhits) + "q"
    elif Hits >= thits:
        return str("%0." + str(Decimal) + "f") % (Hits / thits) + "t"
    elif Hits >= bhits:
        return str("%0." + str(Decimal) + "f") % (Hits / bhits) + "b"
    elif Hits >= mhits:
        return str("%0." + str(Decimal) + "f") % (Hits / mhits) + "m"
    elif Hits >= khits:
        return str("%0." + str(Decimal) + "f") % (Hits / khits) + "k"
    elif Hits == 0:
        return str("%d" % 0)
    else:
        return str("%d" % Hits)


def fPerc(lVal=0, rVal=0, Decimal=2):
    if rVal > 0:
        return str("%0." + str(Decimal) + "f") % (100 * (lVal / rVal)) + "%"
    else:
        return str("%0." + str(Decimal) + "f") % 100 + "%"


def calculate_allocation_units(*args):
    allocation_units = 4096
    while True:
        values = tuple(map(lambda arg: int(arg / allocation_units), args))
        if all(v < 2 ** 31 for v in values):
            break

        allocation_units *= 2

    return allocation_units, values


def get_zfs_arc_miss_percent(kstat):
    arc_hits = kstat["kstat.zfs.misc.arcstats.hits"]
    arc_misses = kstat["kstat.zfs.misc.arcstats.misses"]
    arc_read = arc_hits + arc_misses
    if arc_read > 0:
        hit_percent = float(100 * arc_hits / arc_read)
        miss_percent = 100 - hit_percent
        return miss_percent
    return 0


mib_builder = pysnmp.smi.builder.MibBuilder()
mib_sources = mib_builder.getMibSources() + (pysnmp.smi.builder.DirMibSource("/usr/local/share/pysnmp/mibs"),)
mib_builder.setMibSources(*mib_sources)
mib_builder.loadModules("FREENAS-MIB")
mib_builder.loadModules("LM-SENSORS-MIB")
zpool_health_type = mib_builder.importSymbols("FREENAS-MIB", "ZPoolHealthType")[0]

agent = netsnmpagent.netsnmpAgent(
    AgentName="FreeNASAgent",
    MIBFiles=[
        "/usr/local/share/snmp/mibs/FREENAS-MIB.txt", "/usr/local/share/snmp/mibs/LM-SENSORS-MIB.txt"
    ],
)

zpool_table = agent.Table(
    oidstr="FREENAS-MIB::zpoolTable",
    indexes=[
        agent.Integer32()
    ],
    columns=[
        (1, agent.Integer32()),
        (2, agent.DisplayString()),
        (3, agent.Integer32()),
        (4, agent.Integer32()),
        (5, agent.Integer32()),
        (6, agent.Integer32()),
        (7, agent.Integer32()),
        (8, agent.Counter64()),
        (9, agent.Counter64()),
        (10, agent.Counter64()),
        (11, agent.Counter64()),
        (12, agent.Counter64()),
        (13, agent.Counter64()),
        (14, agent.Counter64()),
        (15, agent.Counter64()),
    ],
)

dataset_table = agent.Table(
    oidstr="FREENAS-MIB::datasetTable",
    indexes=[
        agent.Integer32()
    ],
    columns=[
        (1, agent.Integer32()),
        (2, agent.DisplayString()),
        (3, agent.Integer32()),
        (4, agent.Integer32()),
        (5, agent.Integer32()),
        (6, agent.Integer32()),
    ],
)

zvol_table = agent.Table(
    oidstr="FREENAS-MIB::zvolTable",
    indexes=[
        agent.Integer32()
    ],
    columns=[
        (1, agent.Integer32()),
        (2, agent.DisplayString()),
        (3, agent.Integer32()),
        (4, agent.Integer32()),
        (5, agent.Integer32()),
        (6, agent.Integer32()),
        (7, agent.Integer32()),
    ],
)

lm_sensors_table = None
if osc.IS_FREEBSD:
    lm_sensors_table = agent.Table(
        oidstr="LM-SENSORS-MIB::lmTempSensorsTable",
        indexes=[
            agent.Integer32(),
        ],
        columns=[
            (1, agent.Integer32()),
            (2, agent.DisplayString()),
            (3, agent.Unsigned32()),
        ]
    )

hdd_temp_table = agent.Table(
    oidstr="FREENAS-MIB::hddTempTable",
    indexes=[
        agent.Integer32(),
    ],
    columns=[
        (2, agent.DisplayString()),
        (3, agent.Unsigned32()),
    ]
)

interface_top_host_table = agent.Table(
    oidstr="FREENAS-MIB::interfaceTopHostTable",
    indexes=[
        agent.Integer32(),
    ],
    columns=[
        (2, agent.DisplayString()),
        (3, agent.DisplayString()),
        (4, agent.Unsigned32()),
        (5, agent.DisplayString()),
        (6, agent.Unsigned32()),
        (7, agent.Unsigned32()),
        (8, agent.Unsigned32()),
        (9, agent.Unsigned32()),
        (10, agent.Unsigned32()),
        (11, agent.Unsigned32()),
        (12, agent.Unsigned32()),
    ]
)

zfs_arc_size = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcSize")
zfs_arc_meta = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcMeta")
zfs_arc_data = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcData")
zfs_arc_hits = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcHits")
zfs_arc_misses = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcMisses")
zfs_arc_c = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcC")
zfs_arc_p = agent.Unsigned32(oidstr="FREENAS-MIB::zfsArcP")
zfs_arc_miss_percent = agent.DisplayString(oidstr="FREENAS-MIB::zfsArcMissPercent")
zfs_arc_cache_hit_ratio = agent.DisplayString(oidstr="FREENAS-MIB::zfsArcCacheHitRatio")
zfs_arc_cache_miss_ratio = agent.DisplayString(oidstr="FREENAS-MIB::zfsArcCacheMissRatio")

zfs_l2arc_hits = agent.Counter32(oidstr="FREENAS-MIB::zfsL2ArcHits")
zfs_l2arc_misses = agent.Counter32(oidstr="FREENAS-MIB::zfsL2ArcMisses")
zfs_l2arc_read = agent.Counter32(oidstr="FREENAS-MIB::zfsL2ArcRead")
zfs_l2arc_write = agent.Counter32(oidstr="FREENAS-MIB::zfsL2ArcWrite")
zfs_l2arc_size = agent.Unsigned32(oidstr="FREENAS-MIB::zfsL2ArcSize")

zfs_zilstat_ops1 = agent.Counter64(oidstr="FREENAS-MIB::zfsZilstatOps1sec")
zfs_zilstat_ops5 = agent.Counter64(oidstr="FREENAS-MIB::zfsZilstatOps5sec")
zfs_zilstat_ops10 = agent.Counter64(oidstr="FREENAS-MIB::zfsZilstatOps10sec")


class ZpoolIoThread(threading.Thread):
    def __init__(self):
        super().__init__()

        self.daemon = True

        self.stop_event = threading.Event()

        self.lock = threading.Lock()
        self.values_overall = defaultdict(lambda: defaultdict(lambda: 0))
        self.values_1s = defaultdict(lambda: defaultdict(lambda: 0))

    def run(self):
        zfs = libzfs.ZFS()
        while not self.stop_event.wait(1.0):
            with self.lock:
                previous_values = copy.deepcopy(self.values_overall)

                for pool in zfs.pools:
                    self.values_overall[pool.name] = {
                        "read_ops": pool.root_vdev.stats.ops[libzfs.ZIOType.READ],
                        "write_ops": pool.root_vdev.stats.ops[libzfs.ZIOType.WRITE],
                        "read_bytes": pool.root_vdev.stats.bytes[libzfs.ZIOType.READ],
                        "write_bytes": pool.root_vdev.stats.bytes[libzfs.ZIOType.WRITE],
                    }

                    if pool.name in previous_values:
                        for k in ["read_ops", "write_ops", "read_bytes", "write_bytes"]:
                            self.values_1s[pool.name][k] = (
                                self.values_overall[pool.name][k] -
                                previous_values[pool.name][k]
                            )

    def get_values(self):
        with self.lock:
            return copy.deepcopy(self.values_overall), copy.deepcopy(self.values_1s)


class ZilstatThread(threading.Thread):
    def __init__(self, interval):
        super().__init__()

        self.daemon = True

        self.interval = interval
        self.value = {
            "NBytes": 0,
            "NBytespersec": 0,
            "NMaxRate": 0,
            "BBytes": 0,
            "BBytespersec": 0,
            "BMaxRate": 0,
            "ops": 0,
            "lteq4kb": 0,
            "4to32kb": 0,
            "gteq4kb": 0,
        }

    def run(self):
        zilstatproc = subprocess.Popen(
            ["/usr/local/bin/zilstat", str(self.interval)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        zilstatproc.stdout.readline().strip()
        while zilstatproc.poll() is None:
            output = zilstatproc.stdout.readline().strip().split()
            value = {
                "NBytes": output[0],
                "NBytespersec": output[1],
                "NMaxRate": output[2],
                "BBytes": output[3],
                "BBytespersec": output[4],
                "BMaxRate": output[5],
                "ops": int(output[6]),
                "lteq4kb": output[7],
                "4to32kb": output[8],
                "gteq4kb": output[9],
            }
            self.value = value


class CpuTempThread(threading.Thread):
    def __init__(self, interval):
        super().__init__()

        self.daemon = True

        self.interval = interval
        self.temperatures = []

        self.numcpu = 0
        try:
            self.numcpu = int(sysctl.filter("hw.ncpu")[0].value)
        except Exception as e:
            print(f"Failed to get CPU count: {e!r}")

    def run(self):
        if not self.numcpu:
            return 0

        while True:
            temperatures = []
            try:
                for i in range(self.numcpu):
                    raw_temperature = int(sysctl.filter(f"dev.cpu.{i}.temperature")[0].value)
                    temperatures.append((raw_temperature - 2732) * 100)
            except Exception as e:
                print(f"Failed to get CPU temperature: {e!r}")
                temperatures = []

            self.temperatures = temperatures

            time.sleep(self.interval)


class DiskTempThread(threading.Thread):
    def __init__(self, interval):
        super().__init__()

        self.daemon = True

        self.interval = interval
        self.temperatures = {}

        self.initialized = False
        self.disks = []
        self.powermode = None

    def run(self):
        while True:
            if not self.initialized:
                try:
                    with Client() as c:
                        self.disks = c.call("disk.disks_for_temperature_monitoring")
                        self.powermode = c.call("smart.config")["powermode"]
                except Exception as e:
                    print(f"Failed to query disks for temperature monitoring: {e!r}")
                else:
                    self.initialized = True

            if not self.initialized:
                time.sleep(self.interval)
                continue

            if not self.disks:
                return

            try:
                with Client() as c:
                    self.temperatures = {
                        disk: temperature * 1000
                        for disk, temperature in c.call("disk.temperatures", self.disks, self.powermode).items()
                        if temperature is not None
                    }
            except Exception as e:
                print(f"Failed to collect disks temperatures: {e!r}")
                self.temperatures = {}

            time.sleep(self.interval)


class IftopThread(threading.Thread):
    def __init__(self):
        super().__init__()

        self.daemon = True

        self.stats = {}

    def run(self):
        while True:
            try:
                with Client() as c:
                    interfaces = [i["name"] for i in c.call("interface.query")]
            except Exception as e:
                print(f"Failed to query interfaces for iftop monitoring: {e!r}")
                time.sleep(10)
            else:
                break

        for interface in interfaces:
            IftopInterfaceThread(interface, self.stats).start()


IftopInterfaceStat = namedtuple(
    "IftopInterface",
    ["local_address", "local_port", "remote_address", "remote_port", "in_last_2s", "out_last_2s", "in_last_10s",
     "out_last_10s", "in_last_40s", "out_last_40s"]
)


class IftopInterfaceThread(threading.Thread):
    def __init__(self, interface, stats):
        super().__init__()

        self.daemon = True

        self.interface = interface
        self.stats = stats

    def run(self):
        while True:
            try:
                master, slave = pty.openpty()
                try:
                    p = subprocess.Popen(
                        [
                            "iftop",
                            "-n",           # Don't do hostname lookups
                            "-N",           # Do not resolve port number to service names
                            "-P",           # Turn on port display
                            "-B",           # Display bandwidth rates in bytes/sec rather than bits/sec
                            "-i", self.interface,
                            "-t",           # use text interface without ncurses
                            "-L", "10",     # number of lines to print
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=slave,
                        stderr=subprocess.DEVNULL,
                        encoding="utf-8",
                        errors="ignore",
                        preexec_fn=os.setsid,
                    )
                    try:
                        os.close(slave)
                        with os.fdopen(master, "r", encoding="utf-8", errors="ignore") as f:
                            data = []
                            while True:
                                line = f.readline()
                                if not line:
                                    break

                                if line.startswith("-" * 80):
                                    if (
                                            len(data) % 2 == 0 and
                                            all(len(v.split()) == (7 if i % 2 == 0 else 6) for i, v in enumerate(data))
                                    ):
                                        self.stats[self.interface] = self._handle_data(data)

                                    data = []
                                else:
                                    data.append(line)
                    finally:
                        p.wait()
                        print(f"iftop for {self.interface} returned {p.returncode}")
                finally:
                    with contextlib.suppress(OSError):
                        os.close(master)
                    with contextlib.suppress(OSError):
                        os.close(slave)
            except Exception as e:
                print(f"Failed to run iftop for {self.interface}: {e!r}")

            time.sleep(10)

    def _handle_data(self, data):
        stats = []
        for line1, line2 in zip(data[::2], data[1::2]):
            _, local, _, out_last_2s, out_last_10s, out_last_40s, _ = line1.split()
            remote, _, in_last_2s, in_last_10s, in_last_40s, _ = line2.split()
            local_address, local_port = local.split(":")
            remote_address, remote_port = remote.split(":")
            stats.append(IftopInterfaceStat(
                local_address=local_address,
                local_port=int(local_port),
                remote_address=remote_address,
                remote_port=int(remote_port),
                in_last_2s=self._handle_bw(in_last_2s),
                out_last_2s=self._handle_bw(out_last_2s),
                in_last_10s=self._handle_bw(in_last_10s),
                out_last_10s=self._handle_bw(out_last_10s),
                in_last_40s=self._handle_bw(in_last_40s),
                out_last_40s=self._handle_bw(out_last_40s),
            ))

        return stats

    def _handle_bw(self, bw):
        return humanfriendly.parse_size(bw, binary=True)


if __name__ == "__main__":
    with Client() as c:
        config = c.call("snmp.config")

    zfs = libzfs.ZFS()

    zpool_io_thread = ZpoolIoThread()
    zpool_io_thread.start()

    zilstat_1_thread = None
    zilstat_5_thread = None
    zilstat_10_thread = None

    if osc.IS_FREEBSD:
        if config["zilstat"]:
            zilstat_1_thread = ZilstatThread(1)
            zilstat_5_thread = ZilstatThread(5)
            zilstat_10_thread = ZilstatThread(10)

            zilstat_1_thread.start()
            zilstat_5_thread.start()
            zilstat_10_thread.start()

    cpu_temp_thread = None
    if osc.IS_FREEBSD:
        cpu_temp_thread = CpuTempThread(10)
        cpu_temp_thread.start()

    disk_temp_thread = DiskTempThread(300)
    disk_temp_thread.start()

    iftop_thread = None
    if config["iftop"]:
        iftop_thread = IftopThread()
        iftop_thread.start()

    agent.start()

    last_update_at = datetime.min
    while True:
        agent.check_and_process()

        if datetime.utcnow() - last_update_at > timedelta(seconds=1):
            zpool_io_overall, zpool_io_1sec = zpool_io_thread.get_values()

            datasets = []
            zvols = []
            zpool_table.clear()
            for i, zpool in enumerate(zfs.pools):
                row = zpool_table.addRow([agent.Integer32(i + 1)])
                row.setRowCell(1, agent.Integer32(i + 1))
                row.setRowCell(2, agent.DisplayString(zpool.properties["name"].value))
                allocation_units, \
                    (
                        size,
                        used,
                        available
                    ) = calculate_allocation_units(
                        int(zpool.properties["size"].rawvalue),
                        int(zpool.properties["allocated"].rawvalue),
                        int(zpool.properties["free"].rawvalue),
                    )
                row.setRowCell(3, agent.Integer32(allocation_units))
                row.setRowCell(4, agent.Integer32(size))
                row.setRowCell(5, agent.Integer32(used))
                row.setRowCell(6, agent.Integer32(available))
                row.setRowCell(7, agent.Integer32(zpool_health_type.namedValues.getValue(
                    zpool.properties["health"].value.lower())))
                row.setRowCell(8, agent.Counter64(zpool_io_overall[zpool.name]["read_ops"]))
                row.setRowCell(9, agent.Counter64(zpool_io_overall[zpool.name]["write_ops"]))
                row.setRowCell(10, agent.Counter64(zpool_io_overall[zpool.name]["read_bytes"]))
                row.setRowCell(11, agent.Counter64(zpool_io_overall[zpool.name]["write_bytes"]))
                row.setRowCell(12, agent.Counter64(zpool_io_1sec[zpool.name]["read_ops"]))
                row.setRowCell(13, agent.Counter64(zpool_io_1sec[zpool.name]["write_ops"]))
                row.setRowCell(14, agent.Counter64(zpool_io_1sec[zpool.name]["read_bytes"]))
                row.setRowCell(15, agent.Counter64(zpool_io_1sec[zpool.name]["write_bytes"]))

                for dataset in zpool.root_dataset.children_recursive:
                    if dataset.type == libzfs.DatasetType.FILESYSTEM:
                        datasets.append(dataset)
                    if dataset.type == libzfs.DatasetType.VOLUME:
                        zvols.append(dataset)

            dataset_table.clear()
            for i, dataset in enumerate(datasets):
                row = dataset_table.addRow([agent.Integer32(i + 1)])
                row.setRowCell(1, agent.Integer32(i + 1))
                row.setRowCell(2, agent.DisplayString(dataset.properties["name"].value))
                allocation_units, (
                    size,
                    used,
                    available
                ) = calculate_allocation_units(
                    int(dataset.properties["used"].rawvalue) + int(dataset.properties["available"].rawvalue),
                    int(dataset.properties["used"].rawvalue),
                    int(dataset.properties["available"].rawvalue),
                )
                row.setRowCell(3, agent.Integer32(allocation_units))
                row.setRowCell(4, agent.Integer32(size))
                row.setRowCell(5, agent.Integer32(used))
                row.setRowCell(6, agent.Integer32(available))

            zvol_table.clear()
            for i, zvol in enumerate(zvols):
                row = zvol_table.addRow([agent.Integer32(i + 1)])
                row.setRowCell(1, agent.Integer32(i + 1))
                row.setRowCell(2, agent.DisplayString(zvol.properties["name"].value))
                allocation_units, (
                    volsize,
                    used,
                    available,
                    referenced
                ) = calculate_allocation_units(
                    int(zvol.properties["volsize"].rawvalue),
                    int(zvol.properties["used"].rawvalue),
                    int(zvol.properties["available"].rawvalue),
                    int(zvol.properties["referenced"].rawvalue),
                )
                row.setRowCell(3, agent.Integer32(allocation_units))
                row.setRowCell(4, agent.Integer32(volsize))
                row.setRowCell(5, agent.Integer32(used))
                row.setRowCell(6, agent.Integer32(available))
                row.setRowCell(7, agent.Integer32(referenced))

            if lm_sensors_table:
                lm_sensors_table.clear()
                temperatures = []
                if cpu_temp_thread:
                    for i, temp in enumerate(cpu_temp_thread.temperatures.copy()):
                        temperatures.append((f"CPU{i}", temp))
                if disk_temp_thread:
                    temperatures.extend(list(disk_temp_thread.temperatures.items()))
                for i, (name, temp) in enumerate(temperatures):
                    row = lm_sensors_table.addRow([agent.Integer32(i + 1)])
                    row.setRowCell(1, agent.Integer32(i + 1))
                    row.setRowCell(2, agent.DisplayString(name))
                    row.setRowCell(3, agent.Unsigned32(temp))

            if hdd_temp_table:
                hdd_temp_table.clear()
                if disk_temp_thread:
                    for i, (name, temp) in enumerate(list(disk_temp_thread.temperatures.items())):
                        row = hdd_temp_table.addRow([agent.Integer32(i + 1)])
                        row.setRowCell(2, agent.DisplayString(name))
                        row.setRowCell(3, agent.Unsigned32(temp))

            if interface_top_host_table:
                interface_top_host_table.clear()
                if iftop_thread:
                    i = 1
                    for interface, stats in list(iftop_thread.stats.items()):
                        for stat in stats:
                            row = interface_top_host_table.addRow([agent.Integer32(i)])
                            row.setRowCell(2, agent.DisplayString(interface))
                            row.setRowCell(3, agent.DisplayString(stat.local_address))
                            row.setRowCell(4, agent.Unsigned32(stat.local_port))
                            row.setRowCell(5, agent.DisplayString(stat.remote_address))
                            row.setRowCell(6, agent.Unsigned32(stat.remote_port))
                            row.setRowCell(7, agent.Unsigned32(stat.in_last_2s))
                            row.setRowCell(8, agent.Unsigned32(stat.out_last_2s))
                            row.setRowCell(9, agent.Unsigned32(stat.in_last_10s))
                            row.setRowCell(10, agent.Unsigned32(stat.out_last_10s))
                            row.setRowCell(11, agent.Unsigned32(stat.in_last_40s))
                            row.setRowCell(12, agent.Unsigned32(stat.out_last_40s))
                            i += 1

            kstat = get_Kstat()
            arc_efficiency = get_arc_efficiency(kstat)

            zfs_arc_size.update(kstat["kstat.zfs.misc.arcstats.size"] / 1024)
            zfs_arc_meta.update(kstat["kstat.zfs.misc.arcstats.arc_meta_used"] / 1024)
            zfs_arc_data.update(kstat["kstat.zfs.misc.arcstats.data_size"] / 1024)
            zfs_arc_hits.update(kstat["kstat.zfs.misc.arcstats.hits"] % 2 ** 32)
            zfs_arc_misses.update(kstat["kstat.zfs.misc.arcstats.misses"] % 2 ** 32)
            zfs_arc_c.update(kstat["kstat.zfs.misc.arcstats.c"] / 1024)
            zfs_arc_p.update(kstat["kstat.zfs.misc.arcstats.p"] / 1024)
            zfs_arc_miss_percent.update(str(get_zfs_arc_miss_percent(kstat)).encode("ascii"))
            zfs_arc_cache_hit_ratio.update(str(arc_efficiency["cache_hit_ratio"]["per"][:-1]).encode("ascii"))
            zfs_arc_cache_miss_ratio.update(str(arc_efficiency["cache_miss_ratio"]["per"][:-1]).encode("ascii"))

            zfs_l2arc_hits.update(int(kstat["kstat.zfs.misc.arcstats.l2_hits"] % 2 ** 32))
            zfs_l2arc_misses.update(int(kstat["kstat.zfs.misc.arcstats.l2_misses"] % 2 ** 32))
            zfs_l2arc_read.update(int(kstat["kstat.zfs.misc.arcstats.l2_read_bytes"] / 1024 % 2 ** 32))
            zfs_l2arc_write.update(int(kstat["kstat.zfs.misc.arcstats.l2_write_bytes"] / 1024 % 2 ** 32))
            zfs_l2arc_size.update(int(kstat["kstat.zfs.misc.arcstats.l2_asize"] / 1024))

            if zilstat_1_thread:
                zfs_zilstat_ops1.update(zilstat_1_thread.value["ops"])
            if zilstat_5_thread:
                zfs_zilstat_ops5.update(zilstat_5_thread.value["ops"])
            if zilstat_10_thread:
                zfs_zilstat_ops10.update(zilstat_10_thread.value["ops"])

            last_update_at = datetime.utcnow()
