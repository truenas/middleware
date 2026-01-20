from types import MappingProxyType

# We are essentially
# copying the same logic in the upstream `arc_summary.py`
# and "arcstat" script provided by ZFS but pulling out the
# values we're interested in.
# The reason why we're doing this ourselves is, at time of
# writing, netdata's calculation of similar values is wrong.
# Furthermore, the `arc_summary.py` script makes no attempt
# at explaining these values and so to keep things as simple
# as possible (without confusing the end-user) we're going to
# simplify what we consider "easily understood" ZFS ARC memory
# info without delving into the low-level details.
_4GiB = 4294967296


ArcStatDescriptions: MappingProxyType[str, str] = MappingProxyType(
    {
        # Copy and pasted directly from "arcstat" python
        # script shipped with openZFS. It'd be really nice
        # if they provided an upstream python library that we
        # could use so we wouldn't have to, quite literally,
        # copy and paste the same calucation logic here. But
        # alas, this will have to do for now.
        "free": "ARC free memory",
        "avail": "ARC available memory",
        "size": "ARC size",
        "dread": "Demand accesses per second",
        "ddread": "Demand data accesses per second",
        "dmread": "Demand metadata accesses per second",
        "ddhit": "Demand data hits per second",
        "ddioh": "Demand data I/O hits per second",
        "ddmis": "Demand data misses per second",
        "ddh%": "Demand data hit percentage",
        "ddi%": "Demand data I/O hit percentage",
        "ddm%": "Demand data miss percentage",
        "dmhit": "Demand metadata hits per second",
        "dmioh": "Demand metadata I/O hits per second",
        "dmmis": "Demand metadata misses per second",
        "dmh%": "Demand metadata hit percentage",
        "dmi%": "Demand metadata I/O hit percentage",
        "dmm%": "Demand metadata miss percentage",
        "l2hits": "L2ARC hits per second",
        "l2miss": "L2ARC misses per second",
        "l2read": "Total L2ARC accesses per second",
        "l2hit%": "L2ARC access hit percentage",
        "l2miss%": "L2ARC access miss percentage",
        "l2bytes": "Bytes read per second from the L2ARC",
        "l2wbytes": "Bytes written per second to the L2ARC"
    }
)


def do_round(dividend: int, divisor: int, to_decimal_place: int = 2) -> float:
    return round((dividend / divisor), to_decimal_place)


def calculate_arc_demand_stats_impl(st: dict[str, int], intv: int) -> dict[str, int | float]:
    v: dict[str, int | float] = dict()
    v["dread"] = (
        do_round((st["demand_data_hits"] + st["demand_metadata_hits"]), intv)
        + do_round((st["demand_data_iohits"] + st["demand_metadata_iohits"]), intv)
        + do_round((st["demand_data_misses"] + st["demand_metadata_misses"]), intv)
    )
    v["ddhit"] = do_round(st["demand_data_hits"], intv)
    v["ddioh"] = do_round(st["demand_data_iohits"], intv)
    v["ddmis"] = do_round(st["demand_data_misses"], intv)
    v["ddread"] = v["ddhit"] + v["ddioh"] + v["ddmis"]
    v["ddh%"] = v["ddi%"] = v["ddm%"] = 0.0
    if v["ddread"] > 0:
        v["ddh%"] = do_round(int(100 * v["ddhit"]), int(v["ddread"]))
        v["ddi%"] = do_round(int(100 * v["ddioh"]), int(v["ddread"]))
        v["ddm%"] = 100 - v["ddh%"] - v["ddi%"]

    v["dmhit"] = do_round(st["demand_metadata_hits"], intv)
    v["dmioh"] = do_round(st["demand_metadata_iohits"], intv)
    v["dmmis"] = do_round(st["demand_metadata_misses"], intv)
    v["dmread"] = v["dmhit"] + v["dmioh"] + v["dmmis"]
    v["dmh%"] = v["dmi%"] = v["dmm%"] = 0.0
    if v["dmread"] > 0:
        v["dmh%"] = do_round(int(100 * v["dmhit"]), int(v["dmread"]))
        v["dmi%"] = do_round(int(100 * v["dmioh"]), int(v["dmread"]))
        v["dmm%"] = 100 - v["dmh%"] - v["dmi%"]

    return v


def calculate_l2arc_stats_impl(st: dict[str, int], intv: int) -> dict[str, int | float]:
    v = {
        "l2hits": 0,
        "l2miss": 0,
        "l2read": 0,
        "l2hit%": 0.0,
        "l2miss%": 0.0,
        "l2bytes": 0,
        "l2wbytes": 0,
    }
    if st.get("l2_size"):
        v["l2bytes"] = do_round(st["l2_read_bytes"], intv)
        v["l2wbytes"] = do_round(st["l2_write_bytes"], intv)
        v["l2hits"] = do_round(st["l2_hits"], intv)
        v["l2miss"] = do_round(st["l2_misses"], intv)
        v["l2read"] = v["l2hits"] + v["l2miss"]
        v["l2hit%"] = v["l2miss%"] = 0.0
        if v["l2read"] > 0:
            v["l2hit%"] = do_round(int(100 * v["l2hits"]), int(v["l2read"]))
            v["l2miss%"] = 100 - v["l2hit%"]
    return v


def calculate_arc_stats_impl(st: dict[str, int], intv: int) -> dict[str, tuple[int | float, str]]:
    v: dict[str, int | float] = {
        "free": st["memory_free_bytes"],
        "avail": st["memory_available_bytes"],
        "size": st["size"],
    }
    v.update(calculate_arc_demand_stats_impl(st, intv))
    v.update(calculate_l2arc_stats_impl(st, intv))

    return {vname: (val, ArcStatDescriptions[vname]) for vname, val in v.items()}


def read_procfs_st() -> dict[str, int]:
    rv = dict()
    with open("/proc/spl/kstat/zfs/arcstats") as f:
        for lineno, line in filter(lambda x: x[0] > 2, enumerate(f, start=1)):
            try:
                name, _, value = line.strip().split()
                rv[name.strip()] = int(value)
            except ValueError:
                continue
    return rv


def get_arc_stats(intv: int = 1) -> dict[str, tuple[int | float, str]]:
    return calculate_arc_stats_impl(read_procfs_st(), intv)
