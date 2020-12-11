from middlewared.schema import accepts, Dataset, Dict, Int, Str
from middlewared.service import item_method, Service


class ReplicationService(Service):

    @item_method
    @accepts(
        Int("id"),
        Dict(
            "replication_restore",
            Str("name", required=True),
            Dataset("target_dataset", required=True),
            strict=True,
        )
    )
    async def restore(self, id, data):
        """
        Create the opposite of replication task `id` (PULL if it was PUSH and vice versa).
        """
        replication_task = await self.middleware.call("replication.query", [["id", "=", id]], {"get": True})

        if replication_task["direction"] == "PUSH":
            data["direction"] = "PULL"
            data["naming_schema"] = list(
                {pst["naming_schema"] for pst in replication_task["periodic_snapshot_tasks"]} |
                set(replication_task["also_include_naming_schema"])
            )
        else:
            data["direction"] = "PUSH"
            data["also_include_naming_schema"] = replication_task["naming_schema"]

        data["source_datasets"], _ = (
            await self.middleware.call("zettarepl.reverse_source_target_datasets",
                                       replication_task["source_datasets"],
                                       replication_task["target_dataset"])
        )

        for k in ["transport", "ssh_credentials", "netcat_active_side", "netcat_active_side_listen_address",
                  "netcat_active_side_port_min", "netcat_active_side_port_max", "netcat_passive_side_connect_address",
                  "recursive", "properties", "replicate", "compression", "large_block", "embed", "compressed",
                  "retries"]:
            data[k] = replication_task[k]

        if data["ssh_credentials"] is not None:
            data["ssh_credentials"] = data["ssh_credentials"]["id"]

        data["retention_policy"] = "NONE"
        data["auto"] = False
        data["enabled"] = False  # Do not run it automatically

        return await self.middleware.call("replication.create", data)
