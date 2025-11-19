#!/usr/bin/env python3
import threading
import time
import contextlib
import os

import libzfs
import netsnmpagent
import pysnmp.hlapi  # noqa
import pysnmp.smi

from truenas_api_client import Client
from middlewared.utils.disk_temperatures import get_disks_temperatures_for_snmp


def get_kstat():
    kstat = {}
    try:
        with open("/proc/spl/kstat/zfs/arcstats") as f:
            for lineno, line in enumerate(f, start=1):
                if lineno > 2 and (info := line.strip()):
                    name, _, data = info.split()
                    kstat[f"kstat.zfs.misc.arcstats.{name}"] = int(data)
    except Exception:
        return kstat
    else:
        kstat["vfs.zfs.version.spa"] = 5000

    return kstat


def get_arc_efficiency(kstat):
    if not kstat.get("vfs.zfs.version.spa"):
        return

    output = {}
    prefix = 'kstat.zfs.misc.arcstats'
    arc_hits = kstat[f"{prefix}.hits"]
    arc_misses = kstat[f"{prefix}.misses"]
    demand_data_hits = kstat[f"{prefix}.demand_data_hits"]
    demand_data_misses = kstat[f"{prefix}.demand_data_misses"]
    demand_metadata_hits = kstat[f"{prefix}.demand_metadata_hits"]
    demand_metadata_misses = kstat[f"{prefix}.demand_metadata_misses"]
    mfu_ghost_hits = kstat[f"{prefix}.mfu_ghost_hits"]
    mfu_hits = kstat[f"{prefix}.mfu_hits"]
    mru_ghost_hits = kstat[f"{prefix}.mru_ghost_hits"]
    mru_hits = kstat[f"{prefix}.mru_hits"]
    prefetch_data_hits = kstat[f"{prefix}.prefetch_data_hits"]
    prefetch_data_misses = kstat[f"{prefix}.prefetch_data_misses"]
    prefetch_metadata_hits = kstat[f"{prefix}.prefetch_metadata_hits"]
    prefetch_metadata_misses = kstat[f"{prefix}.prefetch_metadata_misses"]

    anon_hits = arc_hits - (mfu_hits + mru_hits + mfu_ghost_hits + mru_ghost_hits)
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
mib_builder.loadModules("TRUENAS-MIB")

agent = netsnmpagent.netsnmpAgent(
    AgentName="TrueNASAgent",
    MIBFiles=["/usr/local/share/snmp/mibs/TRUENAS-MIB.txt"],
)

zpool_table = agent.Table(
    oidstr="TRUENAS-MIB::zpoolTable",
    indexes=[agent.Integer32()],
    columns=[
        (1, agent.Integer32()),
        (2, agent.DisplayString()),
        (3, agent.DisplayString()),
        (4, agent.Counter64()),
        (5, agent.Counter64()),
        (6, agent.Counter64()),
        (7, agent.Counter64()),
        (8, agent.Counter64()),
        (9, agent.Counter64()),
        (10, agent.Counter64()),
        (11, agent.Counter64()),
    ],
)

zvol_table = agent.Table(
    oidstr="TRUENAS-MIB::zvolTable",
    indexes=[agent.Integer32()],
    columns=[
        (1, agent.Integer32()),
        (2, agent.DisplayString()),
        (3, agent.Counter64()),
        (4, agent.Counter64()),
        (5, agent.Counter64()),
    ],
)

hdd_temp_table = agent.Table(
    oidstr="TRUENAS-MIB::hddTempTable",
    indexes=[
        agent.Integer32(),
    ],
    columns=[
        (2, agent.DisplayString()),
        (3, agent.Unsigned32()),
    ]
)

zfs_arc_size = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcSize")
zfs_arc_meta = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcMeta")
zfs_arc_data = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcData")
zfs_arc_hits = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcHits")
zfs_arc_misses = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcMisses")
zfs_arc_c = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsArcC")
zfs_arc_miss_percent = agent.DisplayString(oidstr="TRUENAS-MIB::zfsArcMissPercent")
zfs_arc_cache_hit_ratio = agent.DisplayString(oidstr="TRUENAS-MIB::zfsArcCacheHitRatio")
zfs_arc_cache_miss_ratio = agent.DisplayString(oidstr="TRUENAS-MIB::zfsArcCacheMissRatio")

zfs_l2arc_hits = agent.Counter32(oidstr="TRUENAS-MIB::zfsL2ArcHits")
zfs_l2arc_misses = agent.Counter32(oidstr="TRUENAS-MIB::zfsL2ArcMisses")
zfs_l2arc_read = agent.Counter32(oidstr="TRUENAS-MIB::zfsL2ArcRead")
zfs_l2arc_write = agent.Counter32(oidstr="TRUENAS-MIB::zfsL2ArcWrite")
zfs_l2arc_size = agent.Unsigned32(oidstr="TRUENAS-MIB::zfsL2ArcSize")

zfs_zilstat_ops1 = agent.Counter64(oidstr="TRUENAS-MIB::zfsZilstatOps1sec")
zfs_zilstat_ops5 = agent.Counter64(oidstr="TRUENAS-MIB::zfsZilstatOps5sec")
zfs_zilstat_ops10 = agent.Counter64(oidstr="TRUENAS-MIB::zfsZilstatOps10sec")


def readZilOpsCount() -> int:
    total = 0
    with open("/proc/spl/kstat/zfs/zil") as f:
        for line in f:
            var, _size, val, *_ = line.split()
            if var in ("zil_itx_metaslab_normal_count", "zil_itx_metaslab_slog_count"):
                total += int(val)
    return total


class ZilstatThread(threading.Thread):
    def __init__(self, interval):
        super().__init__()

        self.daemon = True

        self.interval = interval
        self.value = 0

    def run(self):
        previous = readZilOpsCount()
        while True:
            time.sleep(self.interval)
            current = readZilOpsCount()
            self.value = current - previous
            previous = current


class DiskTempThread(threading.Thread):
    def __init__(self, interval):
        super().__init__()

        self.daemon = True

        self.interval = interval
        self.temperatures = {}

    def run(self):
        while True:
            try:
                with Client() as c:
                    netdata_metrics = c.call('netdata.get_all_metrics')
            except Exception as e:
                print(f"Failed to query netdata metrics: {e!r}")
                self.temperatures = {}
            else:
                self.temperatures = get_disks_temperatures_for_snmp(netdata_metrics)

            time.sleep(self.interval)


def gather_zpool_iostat_info(prev_data, name, zpoolobj):
    r_ops = zpoolobj.root_vdev.stats.ops[libzfs.ZIOType.READ]
    w_ops = zpoolobj.root_vdev.stats.ops[libzfs.ZIOType.WRITE]
    r_bytes = zpoolobj.root_vdev.stats.bytes[libzfs.ZIOType.READ]
    w_bytes = zpoolobj.root_vdev.stats.bytes[libzfs.ZIOType.WRITE]

    # the current values as reported by libzfs
    values_overall = {name: {
        "read_ops": r_ops,
        "write_ops": w_ops,
        "read_bytes": r_bytes,
        "write_bytes": w_bytes,
    }}

    values_1s = {name: {"read_ops": 0, "write_ops": 0, "read_bytes": 0, "write_bytes": 0}}
    for key in prev_data.get(name, ()):
        values_1s[name][key] = (values_overall[name][key] - prev_data[name][key])

    return values_overall, values_1s


def fill_in_zpool_snmp_row_info(idx, name, health, io_overall, io_1s):
    row = zpool_table.addRow([agent.Integer32(idx)])
    row.setRowCell(1, agent.Integer32(idx))
    row.setRowCell(2, agent.DisplayString(name))
    row.setRowCell(3, agent.DisplayString(health))
    row.setRowCell(4, agent.Counter64(io_overall[name]["read_ops"]))
    row.setRowCell(5, agent.Counter64(io_overall[name]["write_ops"]))
    row.setRowCell(6, agent.Counter64(io_overall[name]["read_bytes"]))
    row.setRowCell(7, agent.Counter64(io_overall[name]["write_bytes"]))
    row.setRowCell(8, agent.Counter64(io_1s[name]["read_ops"]))
    row.setRowCell(9, agent.Counter64(io_1s[name]["write_ops"]))
    row.setRowCell(10, agent.Counter64(io_1s[name]["read_bytes"]))
    row.setRowCell(11, agent.Counter64(io_1s[name]["write_bytes"]))


def fill_in_zvol_snmp_row_info(idx, info):
    row = zvol_table.addRow([agent.Integer32(idx)])
    row.setRowCell(1, agent.Integer32(idx))
    row.setRowCell(2, agent.DisplayString(info["name"]))
    row.setRowCell(3, agent.Counter64(info["properties"]["used"]["parsed"]))
    row.setRowCell(4, agent.Counter64(info["properties"]["available"]["parsed"]))
    row.setRowCell(5, agent.Counter64(info["properties"]["referenced"]["parsed"]))


def report_zfs_info(prev_zpool_info):
    zpool_table.clear()
    zvol_table.clear()

    # zpool related information
    with libzfs.ZFS() as z:
        for idx, zpool in enumerate(z.pools, start=1):
            name = zpool.name
            health = zpool.properties["health"].value
            io_overall, io_1s = gather_zpool_iostat_info(prev_zpool_info, name, zpool)
            fill_in_zpool_snmp_row_info(idx, name, health, io_overall, io_1s)
            # be sure and update our zpool io data so next time it's called
            # we calculate the 1sec values properly
            prev_zpool_info.update(io_overall)

        zvols = get_list_of_zvols()
        kwargs = {
            'user_props': False,
            'props': ['used', 'available', 'referenced'],
            'retrieve_children': False,
            'datasets': zvols,
        }
        for idx, ds_info in enumerate(z.datasets_serialized(**kwargs), start=1):
            fill_in_zvol_snmp_row_info(idx, ds_info)


def get_list_of_zvols():
    zvols = set()
    root_dir = '/dev/zvol/'
    with contextlib.suppress(FileNotFoundError):  # no zvols
        for dir_path, unused_dirs, files in os.walk(root_dir):
            for file in filter(lambda x: '@' not in x, files):
                zvols.add(os.path.join(dir_path, file).removeprefix(root_dir).replace('+', ' '))

    return list(zvols)


if __name__ == "__main__":
    zilstat_1_thread = zilstat_5_thread = zilstat_10_thread = None
    with Client() as c:
        if c.call("snmp.config")["zilstat"]:
            zilstat_1_thread = ZilstatThread(1)
            zilstat_5_thread = ZilstatThread(5)
            zilstat_10_thread = ZilstatThread(10)

            zilstat_1_thread.start()
            zilstat_5_thread.start()
            zilstat_10_thread.start()

    # Netdata's disk plugin updates every 5 minutes.
    # Increase the timeout to ensure values are refreshed after the plugin interval.
    disk_temp_thread = DiskTempThread(310)
    disk_temp_thread.start()

    agent.start()

    prev_zpool_info = {}
    last_update_at = int(time.monotonic())
    while True:
        agent.check_and_process()

        if int(time.monotonic()) - last_update_at > 1:
            report_zfs_info(prev_zpool_info)

            if hdd_temp_table:
                hdd_temp_table.clear()
                if disk_temp_thread:
                    for i, (name, temp) in enumerate(list(disk_temp_thread.temperatures.items())):
                        row = hdd_temp_table.addRow([agent.Integer32(i + 1)])
                        row.setRowCell(2, agent.DisplayString(name))
                        row.setRowCell(3, agent.Unsigned32(temp))

            kstat = get_kstat()
            arc_efficiency = get_arc_efficiency(kstat)

            prefix = "kstat.zfs.misc.arcstats"
            zfs_arc_size.update(kstat[f"{prefix}.size"] // 1024)
            zfs_arc_meta.update(kstat[f"{prefix}.arc_meta_used"] // 1024)
            zfs_arc_data.update(kstat[f"{prefix}.data_size"] // 1024)
            zfs_arc_hits.update(int(kstat[f"{prefix}.hits"] % 2 ** 32))
            zfs_arc_misses.update(int(kstat[f"{prefix}.misses"] % 2 ** 32))
            zfs_arc_c.update(kstat[f"{prefix}.c"] // 1024)
            zfs_arc_miss_percent.update(str(get_zfs_arc_miss_percent(kstat)).encode("ascii"))
            zfs_arc_cache_hit_ratio.update(str(arc_efficiency["cache_hit_ratio"]["per"][:-1]).encode("ascii"))
            zfs_arc_cache_miss_ratio.update(str(arc_efficiency["cache_miss_ratio"]["per"][:-1]).encode("ascii"))

            zfs_l2arc_hits.update(int(kstat[f"{prefix}.l2_hits"] % 2 ** 32))
            zfs_l2arc_misses.update(int(kstat[f"{prefix}.l2_misses"] % 2 ** 32))
            zfs_l2arc_read.update(kstat[f"{prefix}.l2_read_bytes"] // 1024 % 2 ** 32)
            zfs_l2arc_write.update(kstat[f"{prefix}.l2_write_bytes"] // 1024 % 2 ** 32)
            zfs_l2arc_size.update(kstat[f"{prefix}.l2_asize"] // 1024)

            if zilstat_1_thread:
                zfs_zilstat_ops1.update(zilstat_1_thread.value)
            if zilstat_5_thread:
                zfs_zilstat_ops5.update(zilstat_5_thread.value)
            if zilstat_10_thread:
                zfs_zilstat_ops10.update(zilstat_10_thread.value)

            last_update_at = int(time.monotonic())
