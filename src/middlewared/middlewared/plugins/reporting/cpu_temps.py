from __future__ import annotations

from middlewared.service import ServiceContext


async def cpu_temperatures(context: ServiceContext) -> dict[str, float]:
    netdata_metrics = await context.middleware.call("netdata.get_all_metrics")
    data: dict[str, float] = {}
    temp_retrieved = False
    for core, cpu_temp in netdata_metrics.get("cputemp.temperatures", {"dimensions": {}})["dimensions"].items():
        data[core] = cpu_temp["value"]
        if not temp_retrieved:
            temp_retrieved = bool(cpu_temp["value"])
    return data if temp_retrieved else {}
