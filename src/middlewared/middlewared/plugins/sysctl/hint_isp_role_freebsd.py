async def setup(middleware):
    if not await middleware.call("keyvalue.get", "run_migration", False):
        return

    if await middleware.call("system.is_ix_hardware"):
        return

    if await middleware.call("keyvalue.get", "hint_isp_role_tunables_created", False):
        return

    tunables = {tunable["var"] for tunable in await middleware.call("tunable.query", [["var", "^", "hint.isp."]])}
    for i in range(0, 4):
        var = f"hint.isp.{i}.role"
        if var in tunables:
            continue

        await middleware.call("tunable.create", {
            "var": var,
            "value": "2",
            "type": "LOADER",
        })

    await middleware.call("keyvalue.set", "hint_isp_role_tunables_created", True)
