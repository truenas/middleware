from middlewared.schema import accepts, Bool, Cron, Dict, Int, List, Patch, Path, Str
from middlewared.service import private, CallError, CRUDService, ValidationErrors
from middlewared.utils.path import is_child
from middlewared.validators import Port, Range, ReplicationSnapshotNamingSchema, Unique


class ReplicationService(CRUDService):

    class Config:
        datastore = "storage.replication"
        datastore_prefix = "repl_"
        datastore_extend = "replication.extend"
        datastore_extend_context = "replication.extend_context"

    @private
    async def extend_context(self):
        return {
            "state": await self.middleware.call("zettarepl.get_state"),
        }

    @private
    async def extend(self, data, context):
        data["periodic_snapshot_tasks"] = [
            {k.replace("task_", ""): v for k, v in task.items()}
            for task in data["periodic_snapshot_tasks"]
        ]

        if data["direction"] == "PUSH":
            data["also_include_naming_schema"] = data["naming_schema"]
            data["naming_schema"] = []
        if data["direction"] == "PULL":
            data["also_include_naming_schema"] = []

        Cron.convert_db_format_to_schedule(data, "schedule", key_prefix="schedule_", begin_end=True)
        Cron.convert_db_format_to_schedule(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        data["state"] = context["state"].get(f"replication_task_{data['id']}", {
            "state": "UNKNOWN",
        })

        return data

    @private
    async def compress(self, data):
        if data["direction"] == "PUSH":
            data["naming_schema"] = data["also_include_naming_schema"]
        del data["also_include_naming_schema"]

        Cron.convert_schedule_to_db_format(data, "schedule", key_prefix="schedule_", begin_end=True)
        Cron.convert_schedule_to_db_format(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        del data["periodic_snapshot_tasks"]

        return data

    @accepts(
        Dict(
            "replication_create",
            Str("direction", enum=["PUSH", "PULL"], required=True),
            Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL", "LEGACY"], required=True),
            Int("ssh_credentials", null=True, default=None),
            Str("netcat_active_side", enum=["LOCAL", "REMOTE"], null=True, default=None),
            Int("netcat_active_side_port_min", null=True, default=None, validators=[Port()]),
            Int("netcat_active_side_port_max", null=True, default=None, validators=[Port()]),
            List("source_datasets", items=[Path("dataset", empty=False)], required=True, empty=False),
            Path("target_dataset", required=True, empty=False),
            Bool("recursive", required=True),
            List("exclude", items=[Path("dataset", empty=False)], default=[]),
            List("periodic_snapshot_tasks", items=[Int("periodic_snapshot_task")], default=[],
                 validators=[Unique()]),
            List("naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])], default=[]),
            List("also_include_naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])], default=[]),
            Bool("auto", required=True),
            Cron("schedule", begin_end=True, null=True, default=None),
            Cron("restrict_schedule", begin_end=True, null=True, default=None),
            Bool("only_matching_schedule", default=False),
            Bool("allow_from_scratch", default=False),
            Bool("hold_pending_snapshots", default=False),
            Str("retention_policy", enum=["SOURCE", "CUSTOM", "NONE"], required=True),
            Int("lifetime_value", null=True, default=None, validators=[Range(min=1)]),
            Str("lifetime_unit", null=True, default=None, enum=["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]),
            Str("compression", enum=["LZ4", "PIGZ", "PLZIP"], null=True, default=None),
            Int("speed_limit", null=True, default=None, validators=[Range(min=1)]),
            Bool("dedup", default=True),
            Bool("large_block", default=True),
            Bool("embed", default=True),
            Bool("compressed", default=True),
            Int("retries", default=5, validators=[Range(min=1)]),
            Bool("enabled", default=True),
            register=True,
            strict=True,
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        verrors.add_child("replication_create", await self._validate(data))

        if verrors:
            raise verrors

        periodic_snapshot_tasks = data["periodic_snapshot_tasks"]
        await self.compress(data)

        id = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data,
            {"prefix": self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id, periodic_snapshot_tasks)

        await self.middleware.call("service.restart", "cron")
        await self.middleware.call("zettarepl.update_tasks")

        return await self._get_instance(id)

    @accepts(Int("id"), Patch(
        "replication_create",
        "replication_update",
        ("attr", {"update": True}),
    ))
    async def do_update(self, id, data):
        old = await self._get_instance(id)

        new = old.copy()
        if new["ssh_credentials"]:
            new["ssh_credentials"] = new["ssh_credentials"]["id"]
        new["periodic_snapshot_tasks"] = [task["id"] for task in new["periodic_snapshot_tasks"]]
        new.update(data)

        verrors = ValidationErrors()
        verrors.add_child("replication_update", await self._validate(new))

        if verrors:
            raise verrors

        periodic_snapshot_tasks = new["periodic_snapshot_tasks"]
        await self.compress(new)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id, periodic_snapshot_tasks)

        await self.middleware.call("service.restart", "cron")
        await self.middleware.call("zettarepl.update_tasks")

        return await self._get_instance(id)

    @accepts(
        Int("id")
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id
        )

        return response

    async def _validate(self, data):
        verrors = ValidationErrors()

        # Direction

        snapshot_tasks = []

        if data["direction"] == "PUSH":
            e, snapshot_tasks = await self._query_periodic_snapshot_tasks(data["periodic_snapshot_tasks"])
            verrors.add_child("periodic_snapshot_tasks", e)

            if data["naming_schema"]:
                verrors.add("naming_schema", "This field has no sense for push replication")

            if data["schedule"]:
                if data["periodic_snapshot_tasks"]:
                    verrors.add("schedule", "Push replication can't be bound to periodic snapshot task and have "
                                            "schedule at the same time")
            else:
                if data["auto"] and not data["periodic_snapshot_tasks"] and data["transport"] != "LEGACY":
                    verrors.add("auto", "Push replication that runs automatically must be either "
                                        "bound to periodic snapshot task or have schedule")

        if data["direction"] == "PULL":
            if data["schedule"]:
                pass
            else:
                if data["auto"]:
                    verrors.add("auto", "Pull replication that runs automatically must have schedule")

            if data["periodic_snapshot_tasks"]:
                verrors.add("periodic_snapshot_tasks", "Pull replication can't be bound to periodic snapshot task")

            if not data["naming_schema"]:
                verrors.add("naming_schema", "Naming schema is required for pull replication")

            if data["also_include_naming_schema"]:
                verrors.add("also_include_naming_schema", "This field has no sense for pull replication")

            if data["hold_pending_snapshots"]:
                verrors.add("hold_pending_snapshots", "Pull replication tasks can't hold pending snapshots because "
                                                      "they don't do source retention")

        # Transport

        if data["transport"] == "SSH+NETCAT":
            if data["netcat_active_side"] is None:
                verrors.add("netcat_active_side", "You must choose active side for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is None:
                verrors.add("netcat_active_side_port_min",
                            "You must specify minimum active side port for SSH+netcat replication")

            if data["netcat_active_side_port_max"] is None:
                verrors.add("netcat_active_side_port_max",
                            "You must specify maximum active side port for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is not None and data["netcat_active_side_port_max"] is not None:
                if data["netcat_active_side_port_min"] > data["netcat_active_side_port_max"]:
                    verrors.add("netcat_active_side_port_max",
                                "Please specify value greater or equal than netcat_active_side_port_min")

            if data["compression"] is not None:
                verrors.add("compression", "Compression is not supported for SSH+netcat replication")

            if data["speed_limit"] is not None:
                verrors.add("speed_limit", "Speed limit is not supported for SSH+netcat replication")
        else:
            if data["netcat_active_side"] is not None:
                verrors.add("netcat_active_side", "This field only has sense for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is not None:
                verrors.add("netcat_active_side_port_min", "This field only has sense for SSH+netcat replication")

            if data["netcat_active_side_port_max"] is not None:
                verrors.add("netcat_active_side_port_max", "This field only has sense for SSH+netcat replication")

        if data["transport"] == "LOCAL":
            if data["ssh_credentials"] is not None:
                verrors.add("ssh_credentials", "Remote credentials have no sense for local replication")

            if data["compression"] is not None:
                verrors.add("compression", "Compression has no sense for local replication")

            if data["speed_limit"] is not None:
                verrors.add("speed_limit", "Speed limit has no sense for local replication")
        else:
            if data["ssh_credentials"] is None:
                verrors.add("ssh_credentials", "SSH Credentials are required for non-local replication")
            else:
                try:
                    await self.middleware.call("keychaincredential.get_of_type", data["ssh_credentials"],
                                               "SSH_CREDENTIALS")
                except CallError as e:
                    verrors.add("ssh_credentials", str(e))

        if data["transport"] == "LEGACY":
            for should_be_true in ["auto", "allow_from_scratch"]:
                if not data[should_be_true]:
                    verrors.add(should_be_true, "Legacy replication does not support disabling this option")

            for should_be_false in ["exclude", "periodic_snapshot_tasks", "naming_schema", "also_include_naming_schema",
                                    "only_matching_schedule", "dedup", "large_block", "embed", "compressed"]:
                if data[should_be_false]:
                    verrors.add(should_be_false, "Legacy replication does not support this option")

            if data["direction"] != "PUSH":
                verrors.add("direction", "Only push application is allowed for Legacy transport")

            if len(data["source_datasets"]) != 1:
                verrors.add("source_datasets", "You can only have one source dataset for legacy replication")

            if data["retries"] != 1:
                verrors.add("retries", "This value should be 1 for legacy replication")

        # Common for all directions and transports

        for i, source_dataset in enumerate(data["source_datasets"]):
            for snapshot_task in snapshot_tasks:
                if is_child(source_dataset, snapshot_task["dataset"]):
                    if data["recursive"]:
                        for exclude in snapshot_task["exclude"]:
                            if exclude not in data["exclude"]:
                                verrors.add("exclude", f"You should exclude {exclude!r} as bound periodic snapshot "
                                                       f"task dataset {snapshot_task['dataset']!r} does")
                    else:
                        if source_dataset in snapshot_task["exclude"]:
                            verrors.add(f"source_datasets.{i}", f"Dataset {source_dataset!r} is excluded by bound "
                                                                f"periodic snapshot task for dataset "
                                                                f"{snapshot_task['dataset']!r}")

        if not data["recursive"] and data["exclude"]:
            verrors.add("exclude", "Excluding child datasets is only supported for recursive replication")

        for i, v in enumerate(data["exclude"]):
            if not any(v.startswith(ds + "/") for ds in data["source_datasets"]):
                verrors.add(f"exclude.{i}", "This dataset is not a child of any of source datasets")

        if data["schedule"]:
            if not data["auto"]:
                verrors.add("schedule", "You can't have schedule for replication that does not run automatically")
        else:
            if data["only_matching_schedule"]:
                verrors.add("only_matching_schedule", "You can't have only-matching-schedule without schedule")

        if data["retention_policy"] == "CUSTOM":
            if data["lifetime_value"] is None:
                verrors.add("lifetime_value", "This field is required for custom retention policy")
            if data["lifetime_unit"] is None:
                verrors.add("lifetime_value", "This field is required for custom retention policy")
        else:
            if data["lifetime_value"] is not None:
                verrors.add("lifetime_value", "This field has no sense for specified retention policy")
            if data["lifetime_unit"] is not None:
                verrors.add("lifetime_unit", "This field has no sense for specified retention policy")

        if data["enabled"]:
            for i, snapshot_task in enumerate(snapshot_tasks):
                if not snapshot_task["enabled"]:
                    verrors.add(
                        f"periodic_snapshot_tasks.{i}",
                        "You can't bind disabled periodic snapshot task to enabled replication task"
                    )

        return verrors

    async def _set_periodic_snapshot_tasks(self, replication_task_id, periodic_snapshot_tasks_ids):
        await self.middleware.call("datastore.delete", "storage.replication_repl_periodic_snapshot_tasks",
                                   [["replication_id", "=", replication_task_id]])
        for periodic_snapshot_task_id in periodic_snapshot_tasks_ids:
            await self.middleware.call(
                "datastore.insert", "storage.replication_repl_periodic_snapshot_tasks",
                {
                    "replication_id": replication_task_id,
                    "task_id": periodic_snapshot_task_id,
                },
            )

    async def _query_periodic_snapshot_tasks(self, ids):
        verrors = ValidationErrors()

        query_result = await self.middleware.call("pool.snapshottask.query", [["id", "in", ids]])

        snapshot_tasks = []
        for i, task_id in enumerate(ids):
            for task in query_result:
                if task["id"] == task_id:
                    snapshot_tasks.append(task)
                    break
            else:
                verrors.add(str(i), "This snapshot task does not exist")

        return verrors, snapshot_tasks

    @accepts(Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL", "LEGACY"], required=True),
             Int("ssh_credentials", null=True, default=None))
    async def list_datasets(self, transport, ssh_credentials=None):
        return await self.middleware.call("zettarepl.list_datasets", transport, ssh_credentials)

    @accepts(Str("dataset", required=True),
             Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL", "LEGACY"], required=True),
             Int("ssh_credentials", null=True, default=None))
    async def create_dataset(self, dataset, transport, ssh_credentials=None):
        return await self.middleware.call("zettarepl.create_dataset", dataset, transport, ssh_credentials)

    # Legacy pair support
    @private
    @accepts(Dict(
        "replication-pair-data",
        Str("hostname", required=True),
        Str("public-key", required=True),
        Str("user"),
    ))
    async def pair(self, data):
        result = await self.middleware.call("keychaincredential.ssh_pair", {
            "remote_hostname": data["hostname"],
            "username": data["user"],
            "public_key": data["public-key"],
        })
        return {
            "ssh_port": result["port"],
            "ssh_hostkey": result["host_key"],
        }
