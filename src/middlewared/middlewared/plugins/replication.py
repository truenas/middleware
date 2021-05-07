from datetime import datetime, time
import os
import re

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import accepts, Bool, Cron, Dataset, Dict, Int, List, Patch, Str
from middlewared.service import item_method, job, private, CallError, CRUDService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.path import is_child
from middlewared.validators import Port, Range, ReplicationSnapshotNamingSchema, Unique


class ReplicationModel(sa.Model):
    __tablename__ = 'storage_replication'

    id = sa.Column(sa.Integer(), primary_key=True)
    repl_target_dataset = sa.Column(sa.String(120))
    repl_recursive = sa.Column(sa.Boolean(), default=False)
    repl_compression = sa.Column(sa.String(120), nullable=True, default="LZ4")
    repl_speed_limit = sa.Column(sa.Integer(), nullable=True, default=None)
    repl_schedule_begin = sa.Column(sa.Time(), nullable=True, default=time(hour=0))
    repl_schedule_end = sa.Column(sa.Time(), nullable=True, default=time(hour=23, minute=45))
    repl_enabled = sa.Column(sa.Boolean(), default=True)
    repl_direction = sa.Column(sa.String(120), default="PUSH")
    repl_transport = sa.Column(sa.String(120), default="SSH")
    repl_ssh_credentials_id = sa.Column(sa.ForeignKey('system_keychaincredential.id'), index=True, nullable=True)
    repl_netcat_active_side = sa.Column(sa.String(120), nullable=True, default=None)
    repl_netcat_active_side_port_min = sa.Column(sa.Integer(), nullable=True)
    repl_netcat_active_side_port_max = sa.Column(sa.Integer(), nullable=True)
    repl_source_datasets = sa.Column(sa.JSON(type=list))
    repl_exclude = sa.Column(sa.JSON(type=list))
    repl_naming_schema = sa.Column(sa.JSON(type=list))
    repl_name_regex = sa.Column(sa.String(120), nullable=True)
    repl_auto = sa.Column(sa.Boolean(), default=True)
    repl_schedule_minute = sa.Column(sa.String(100), nullable=True, default="00")
    repl_schedule_hour = sa.Column(sa.String(100), nullable=True, default="*")
    repl_schedule_daymonth = sa.Column(sa.String(100), nullable=True, default="*")
    repl_schedule_month = sa.Column(sa.String(100), nullable=True, default='*')
    repl_schedule_dayweek = sa.Column(sa.String(100), nullable=True, default="*")
    repl_only_matching_schedule = sa.Column(sa.Boolean())
    repl_readonly = sa.Column(sa.String(120))
    repl_allow_from_scratch = sa.Column(sa.Boolean())
    repl_hold_pending_snapshots = sa.Column(sa.Boolean())
    repl_retention_policy = sa.Column(sa.String(120), default="NONE")
    repl_lifetime_unit = sa.Column(sa.String(120), nullable=True, default='WEEK')
    repl_lifetime_value = sa.Column(sa.Integer(), nullable=True, default=2)
    repl_lifetimes = sa.Column(sa.JSON(type=list))
    repl_large_block = sa.Column(sa.Boolean(), default=True)
    repl_embed = sa.Column(sa.Boolean(), default=False)
    repl_compressed = sa.Column(sa.Boolean(), default=True)
    repl_retries = sa.Column(sa.Integer(), default=5)
    repl_restrict_schedule_minute = sa.Column(sa.String(100), nullable=True, default="00")
    repl_restrict_schedule_hour = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_daymonth = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_month = sa.Column(sa.String(100), nullable=True, default='*')
    repl_restrict_schedule_dayweek = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_begin = sa.Column(sa.Time(), nullable=True, default=time(hour=0))
    repl_restrict_schedule_end = sa.Column(sa.Time(), nullable=True, default=time(hour=23, minute=45))
    repl_netcat_active_side_listen_address = sa.Column(sa.String(120), nullable=True, default=None)
    repl_netcat_passive_side_connect_address = sa.Column(sa.String(120), nullable=True, default=None)
    repl_logging_level = sa.Column(sa.String(120), nullable=True, default=None)
    repl_name = sa.Column(sa.String(120))
    repl_state = sa.Column(sa.Text(), default="{}")
    repl_properties = sa.Column(sa.Boolean(), default=True)
    repl_properties_exclude = sa.Column(sa.JSON(type=list))
    repl_properties_override = sa.Column(sa.JSON())
    repl_replicate = sa.Column(sa.Boolean())
    repl_encryption = sa.Column(sa.Boolean())
    repl_encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    repl_encryption_key_format = sa.Column(sa.String(120), nullable=True)
    repl_encryption_key_location = sa.Column(sa.Text(), nullable=True)

    repl_periodic_snapshot_tasks = sa.relationship('PeriodicSnapshotTaskModel',
                                                   secondary=lambda: ReplicationPeriodicSnapshotTaskModel.__table__)


class ReplicationPeriodicSnapshotTaskModel(sa.Model):
    __tablename__ = 'storage_replication_repl_periodic_snapshot_tasks'

    id = sa.Column(sa.Integer(), primary_key=True)
    replication_id = sa.Column(sa.ForeignKey('storage_replication.id', ondelete='CASCADE'), index=True)
    task_id = sa.Column(sa.ForeignKey('storage_task.id', ondelete='CASCADE'), index=True)


class ReplicationService(CRUDService):

    class Config:
        datastore = "storage.replication"
        datastore_prefix = "repl_"
        datastore_extend = "replication.extend"
        datastore_extend_context = "replication.extend_context"
        cli_namespace = "task.replication"

    @private
    async def extend_context(self, rows, extra):
        return {
            "state": await self.middleware.call("zettarepl.get_state"),
        }

    @private
    async def extend(self, data, context):
        data["periodic_snapshot_tasks"] = [
            {k.replace("task_", ""): v for k, v in task.items()}
            for task in data["periodic_snapshot_tasks"]
        ]

        for task in data["periodic_snapshot_tasks"]:
            Cron.convert_db_format_to_schedule(task, begin_end=True)

        if data["direction"] == "PUSH":
            data["also_include_naming_schema"] = data["naming_schema"]
            data["naming_schema"] = []
        if data["direction"] == "PULL":
            data["also_include_naming_schema"] = []

        Cron.convert_db_format_to_schedule(data, "schedule", key_prefix="schedule_", begin_end=True)
        Cron.convert_db_format_to_schedule(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        if "error" in context["state"]:
            data["state"] = context["state"]["error"]
        else:
            data["state"] = context["state"]["tasks"].get(f"replication_task_{data['id']}", {
                "state": "PENDING",
            })

        data["job"] = data["state"].pop("job", None)

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
            Str("name", required=True),
            Str("direction", enum=["PUSH", "PULL"], required=True),
            Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL"], required=True),
            Int("ssh_credentials", null=True, default=None),
            Str("netcat_active_side", enum=["LOCAL", "REMOTE"], null=True, default=None),
            Str("netcat_active_side_listen_address", null=True, default=None),
            Int("netcat_active_side_port_min", null=True, default=None, validators=[Port()]),
            Int("netcat_active_side_port_max", null=True, default=None, validators=[Port()]),
            Str("netcat_passive_side_connect_address", null=True, default=None),
            List("source_datasets", items=[Dataset("dataset")], empty=False),
            Dataset("target_dataset", required=True),
            Bool("recursive", required=True),
            List("exclude", items=[Dataset("dataset")]),
            Bool("properties", default=True),
            List("properties_exclude", items=[Str("property", empty=False)]),
            Dict("properties_override", additional_attrs=True),
            Bool("replicate", default=False),
            Bool("encryption", default=False),
            Str("encryption_key", null=True, default=None),
            Str("encryption_key_format", enum=["HEX", "PASSPHRASE"], null=True, default=None),
            Str("encryption_key_location", null=True, default=None),
            List("periodic_snapshot_tasks", items=[Int("periodic_snapshot_task")],
                 validators=[Unique()]),
            List("naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])]),
            List("also_include_naming_schema", items=[
                Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])]),
            Str("name_regex", null=True, default=None, empty=False),
            Bool("auto", required=True),
            Cron(
                "schedule",
                defaults={"minute": "00"},
                begin_end=True,
                null=True,
                default=None
            ),
            Cron(
                "restrict_schedule",
                defaults={"minute": "00"},
                begin_end=True,
                null=True,
                default=None
            ),
            Bool("only_matching_schedule", default=False),
            Bool("allow_from_scratch", default=False),
            Str("readonly", enum=["SET", "REQUIRE", "IGNORE"], default="SET"),
            Bool("hold_pending_snapshots", default=False),
            Str("retention_policy", enum=["SOURCE", "CUSTOM", "NONE"], required=True),
            Int("lifetime_value", null=True, default=None, validators=[Range(min=1)]),
            Str("lifetime_unit", null=True, default=None, enum=["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]),
            List("lifetimes", items=[
                Dict(
                    "lifetime",
                    Cron("schedule"),
                    Int("lifetime_value", validators=[Range(min=1)], required=True),
                    Str("lifetime_unit", enum=["HOUR", "DAY", "WEEK", "MONTH", "YEAR"], required=True),
                    strict=True,
                ),
            ]),
            Str("compression", enum=["LZ4", "PIGZ", "PLZIP"], null=True, default=None),
            Int("speed_limit", null=True, default=None, validators=[Range(min=1)]),
            Bool("large_block", default=True),
            Bool("embed", default=False),
            Bool("compressed", default=True),
            Int("retries", default=5, validators=[Range(min=1)]),
            Str("logging_level", enum=["DEBUG", "INFO", "WARNING", "ERROR"], null=True, default=None),
            Bool("enabled", default=True),
            register=True,
            strict=True,
        )
    )
    async def do_create(self, data):
        """
        Create a Replication Task

        Create a Replication Task that will push or pull ZFS snapshots to or from remote host..

        * `name` specifies a name for replication task
        * `direction` specifies whether task will `PUSH` or `PULL` snapshots
        * `transport` is a method of snapshots transfer:
          * `SSH` transfers snapshots via SSH connection. This method is supported everywhere but does not achieve
            great performance
            `ssh_credentials` is a required field for this transport (Keychain Credential ID of type `SSH_CREDENTIALS`)
          * `SSH+NETCAT` uses unencrypted connection for data transfer. This can only be used in trusted networks
            and requires a port (specified by range from `netcat_active_side_port_min` to `netcat_active_side_port_max`)
            to be open on `netcat_active_side`
            `ssh_credentials` is also required for control connection
          * `LOCAL` replicates to or from localhost
        * `source_datasets` is a non-empty list of datasets to replicate snapshots from
        * `target_dataset` is a dataset to put snapshots into. It must exist on target side
        * `recursive` and `exclude` have the same meaning as for Periodic Snapshot Task
        * `properties` control whether we should send dataset properties along with snapshots
        * `periodic_snapshot_tasks` is a list of periodic snapshot task IDs that are sources of snapshots for this
          replication task. Only push replication tasks can be bound to periodic snapshot tasks.
        * `naming_schema` is a list of naming schemas for pull replication
        * `also_include_naming_schema` is a list of naming schemas for push replication
        * `name_regex` will replicate all snapshots which names match specified regular expression
        * `auto` allows replication to run automatically on schedule or after bound periodic snapshot task
        * `schedule` is a schedule to run replication task. Only `auto` replication tasks without bound periodic
          snapshot tasks can have a schedule
        * `restrict_schedule` restricts when replication task with bound periodic snapshot tasks runs. For example,
          you can have periodic snapshot tasks that run every 15 minutes, but only run replication task every hour.
        * Enabling `only_matching_schedule` will only replicate snapshots that match `schedule` or
          `restrict_schedule`
        * `allow_from_scratch` will destroy all snapshots on target side and replicate everything from scratch if none
          of the snapshots on target side matches source snapshots
        * `readonly` controls destination datasets readonly property:
          * `SET` will set all destination datasets to readonly=on after finishing the replication
          * `REQUIRE` will require all existing destination datasets to have readonly=on property
          * `IGNORE` will avoid this kind of behavior
        * `hold_pending_snapshots` will prevent source snapshots from being deleted by retention of replication fails
          for some reason
        * `retention_policy` specifies how to delete old snapshots on target side:
          * `SOURCE` deletes snapshots that are absent on source side
          * `CUSTOM` deletes snapshots that are older than `lifetime_value` and `lifetime_unit`
          * `NONE` does not delete any snapshots
        * `compression` compresses SSH stream. Available only for SSH transport
        * `speed_limit` limits speed of SSH stream. Available only for SSH transport
        * `large_block`, `embed` and `compressed` are various ZFS stream flag documented in `man zfs send`
        * `retries` specifies number of retries before considering replication failed

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.create",
                "params": [{
                    "name": "Work Backup",
                    "direction": "PUSH",
                    "transport": "SSH",
                    "ssh_credentials": [12],
                    "source_datasets", ["data/work"],
                    "target_dataset": "repl/work",
                    "recursive": true,
                    "periodic_snapshot_tasks": [5],
                    "auto": true,
                    "restrict_schedule": {
                        "minute": "0",
                        "hour": "*/2",
                        "dom": "*",
                        "month": "*",
                        "dow": "1,2,3,4,5",
                        "begin": "09:00",
                        "end": "18:00"
                    },
                    "only_matching_schedule": true,
                    "retention_policy": "CUSTOM",
                    "lifetime_value": 1,
                    "lifetime_unit": "WEEK",
                }]
            }
        """

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

        await self.middleware.call("zettarepl.update_tasks")

        return await self._get_instance(id)

    @accepts(Int("id"), Patch(
        "replication_create",
        "replication_update",
        ("attr", {"update": True}),
    ))
    async def do_update(self, id, data):
        """
        Update a Replication Task with specific `id`

        See the documentation for `create` method for information on payload contents

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.update",
                "params": [
                    7,
                    {
                        "name": "Work Backup",
                        "direction": "PUSH",
                        "transport": "SSH",
                        "ssh_credentials": [12],
                        "source_datasets", ["data/work"],
                        "target_dataset": "repl/work",
                        "recursive": true,
                        "periodic_snapshot_tasks": [5],
                        "auto": true,
                        "restrict_schedule": {
                            "minute": "0",
                            "hour": "*/2",
                            "dom": "*",
                            "month": "*",
                            "dow": "1,2,3,4,5",
                            "begin": "09:00",
                            "end": "18:00"
                        },
                        "only_matching_schedule": true,
                        "retention_policy": "CUSTOM",
                        "lifetime_value": 1,
                        "lifetime_unit": "WEEK",
                    }
                ]
            }
        """

        old = await self._get_instance(id)

        new = old.copy()
        if new["ssh_credentials"]:
            new["ssh_credentials"] = new["ssh_credentials"]["id"]
        new["periodic_snapshot_tasks"] = [task["id"] for task in new["periodic_snapshot_tasks"]]
        new.update(data)

        verrors = ValidationErrors()
        verrors.add_child("replication_update", await self._validate(new, id))

        if verrors:
            raise verrors

        periodic_snapshot_tasks = new["periodic_snapshot_tasks"]
        await self.compress(new)

        new.pop("state", None)
        new.pop("job", None)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id, periodic_snapshot_tasks)

        await self.middleware.call("zettarepl.update_tasks")

        return await self._get_instance(id)

    @accepts(
        Int("id")
    )
    async def do_delete(self, id):
        """
        Delete a Replication Task with specific `id`

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.delete",
                "params": [
                    1
                ]
            }
        """

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id
        )

        await self.middleware.call("zettarepl.update_tasks")

        return response

    @item_method
    @accepts(Int("id"), Bool("really_run", default=True, hidden=True))
    @job(logs=True)
    async def run(self, job, id, really_run):
        """
        Run Replication Task of `id`.
        """
        if really_run:
            task = await self._get_instance(id)

            if not task["enabled"]:
                raise CallError("Task is not enabled")

            if task["state"]["state"] == "RUNNING":
                raise CallError("Task is already running")

            if task["state"]["state"] == "HOLD":
                raise CallError("Task is on hold")

        await self.middleware.call("zettarepl.run_replication_task", id, really_run, job)

    @accepts(
        Patch(
            "replication_create",
            "replication_run_onetime",
            ("rm", {"name": "name"}),
            ("rm", {"name": "auto"}),
            ("rm", {"name": "schedule"}),
            ("rm", {"name": "only_matching_schedule"}),
            ("rm", {"name": "enabled"}),
        ),
    )
    @job(logs=True)
    async def run_onetime(self, job, data):
        """
        Run replication task without creating it.
        """

        data["name"] = f"Temporary replication task for job {job.id}"
        data["schedule"] = None
        data["only_matching_schedule"] = False
        data["auto"] = False
        data["enabled"] = True

        verrors = ValidationErrors()
        verrors.add_child("replication_run_onetime", await self._validate(data))

        if verrors:
            raise verrors

        await self.middleware.call("zettarepl.run_onetime_replication_task", job, data)

    async def _validate(self, data, id=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, "", "name", data["name"], id)

        # Direction

        snapshot_tasks = []

        if data["direction"] == "PUSH":
            e, snapshot_tasks = await self._query_periodic_snapshot_tasks(data["periodic_snapshot_tasks"])
            verrors.add_child("periodic_snapshot_tasks", e)

            if data["naming_schema"]:
                verrors.add("naming_schema", "This field has no sense for push replication")

            if not snapshot_tasks and not data["also_include_naming_schema"] and not data["name_regex"]:
                verrors.add(
                    "periodic_snapshot_tasks", "You must at least either bind a periodic snapshot task or provide "
                                               "\"Also Include Naming Schema\" or \"Name Regex\" for push replication "
                                               "task"
                )

            if data["schedule"] is None and data["auto"] and not data["periodic_snapshot_tasks"]:
                verrors.add("auto", "Push replication that runs automatically must be either "
                                    "bound to a periodic snapshot task or have a schedule")

        if data["direction"] == "PULL":
            if data["schedule"] is None and data["auto"]:
                verrors.add("auto", "Pull replication that runs automatically must have a schedule")

            if data["periodic_snapshot_tasks"]:
                verrors.add("periodic_snapshot_tasks", "Pull replication can't be bound to a periodic snapshot task")

            if not data["naming_schema"] and not data["name_regex"]:
                verrors.add("naming_schema", "Naming schema or Name regex are required for pull replication")

            if data["also_include_naming_schema"]:
                verrors.add("also_include_naming_schema", "This field has no sense for pull replication")

            if data["hold_pending_snapshots"]:
                verrors.add("hold_pending_snapshots", "Pull replication tasks can't hold pending snapshots because "
                                                      "they don't do source retention")

        # Transport

        if data["transport"] == "SSH+NETCAT":
            if data["netcat_active_side"] is None:
                verrors.add("netcat_active_side", "You must choose active side for SSH+netcat replication")

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

            for k in ["netcat_active_side_listen_address", "netcat_active_side_port_min", "netcat_active_side_port_max",
                      "netcat_passive_side_connect_address"]:
                if data[k] is not None:
                    verrors.add(k, "This field only has sense for SSH+netcat replication")

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

        # Common for all directions and transports

        for i, source_dataset in enumerate(data["source_datasets"]):
            for snapshot_task in snapshot_tasks:
                if is_child(source_dataset, snapshot_task["dataset"]):
                    if data["recursive"]:
                        for exclude in snapshot_task["exclude"]:
                            if is_child(exclude, source_dataset) and exclude not in data["exclude"]:
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

        if data["replicate"]:
            if not data["recursive"]:
                verrors.add("recursive", "This option is required for full filesystem replication")

            if data["exclude"]:
                verrors.add("exclude", "This option is not supported for full filesystem replication")

            if not data["properties"]:
                verrors.add("properties", "This option is required for full filesystem replication")

        if data["encryption"]:
            for k in ["encryption_key", "encryption_key_format", "encryption_key_location"]:
                if data[k] is None:
                    verrors.add(k, "This property is required when remote dataset encryption is enabled")

        if data["schedule"]:
            if not data["auto"]:
                verrors.add("schedule", "You can't have schedule for replication that does not run automatically")
        else:
            if data["only_matching_schedule"]:
                verrors.add("only_matching_schedule", "You can't have only-matching-schedule without schedule")

        if data["name_regex"]:
            try:
                re.compile(f"({data['name_regex']})$")
            except Exception as e:
                verrors.add("name_regex", f"Invalid regex: {e}")

            if data["naming_schema"] or data["also_include_naming_schema"]:
                verrors.add("name_regex", "Naming regex can't be used with Naming schema")

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
            if data["lifetimes"]:
                verrors.add("lifetimes", "This field has no sense for specified retention policy")

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

    @accepts(Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL"], required=True),
             Int("ssh_credentials", null=True, default=None))
    async def list_datasets(self, transport, ssh_credentials):
        """
        List datasets on remote side

        Accepts `transport` and SSH credentials ID (for non-local transport)

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.list_datasets",
                "params": [
                    "SSH",
                    7
                ]
            }
        """

        return await self.middleware.call("zettarepl.list_datasets", transport, ssh_credentials)

    @accepts(Str("dataset", required=True),
             Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL"], required=True),
             Int("ssh_credentials", null=True, default=None))
    async def create_dataset(self, dataset, transport, ssh_credentials):
        """
        Creates dataset on remote side

        Accepts `dataset` name, `transport` and SSH credentials ID (for non-local transport)

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.create_dataset",
                "params": [
                    "repl/work",
                    "SSH",
                    7
                ]
            }
        """

        return await self.middleware.call("zettarepl.create_dataset", dataset, transport, ssh_credentials)

    @accepts()
    async def list_naming_schemas(self):
        """
        List all naming schemas used in periodic snapshot and replication tasks.
        """
        naming_schemas = []
        for snapshottask in await self.middleware.call("pool.snapshottask.query"):
            naming_schemas.append(snapshottask["naming_schema"])
        for replication in await self.middleware.call("replication.query"):
            naming_schemas.extend(replication["naming_schema"])
            naming_schemas.extend(replication["also_include_naming_schema"])
        return sorted(set(naming_schemas))

    @accepts(
        List("datasets", empty=False, items=[
            Dataset("dataset")
        ]),
        List("naming_schema", empty=False, items=[
            Str("naming_schema", validators=[ReplicationSnapshotNamingSchema()])
        ]),
        Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL"], required=True),
        Int("ssh_credentials", null=True, default=None),
    )
    async def count_eligible_manual_snapshots(self, datasets, naming_schema, transport, ssh_credentials):
        """
        Count how many existing snapshots of `dataset` match `naming_schema`.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.count_eligible_manual_snapshots",
                "params": [
                    "repl/work",
                    ["auto-%Y-%m-%d_%H-%M"],
                    "SSH",
                    4
                ]
            }
        """
        return await self.middleware.call("zettarepl.count_eligible_manual_snapshots", datasets, naming_schema,
                                          transport, ssh_credentials)

    @accepts(
        Str("direction", enum=["PUSH", "PULL"], required=True),
        List("source_datasets", items=[Dataset("dataset")], required=True, empty=False),
        Dataset("target_dataset", required=True),
        Str("transport", enum=["SSH", "SSH+NETCAT", "LOCAL", "LEGACY"], required=True),
        Int("ssh_credentials", null=True, default=None),
    )
    async def target_unmatched_snapshots(self, direction, source_datasets, target_dataset, transport, ssh_credentials):
        """
        Check if target has any snapshots that do not exist on source.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "replication.target_unmatched_snapshots",
                "params": [
                    "PUSH",
                    ["repl/work", "repl/games"],
                    "backup",
                    "SSH",
                    4
                ]
            }

        Returns

            {
                "backup/work": ["auto-2019-10-15_13-00", "auto-2019-10-15_09-00"],
                "backup/games": ["auto-2019-10-15_13-00"],
            }
        """
        return await self.middleware.call("zettarepl.target_unmatched_snapshots", direction, source_datasets,
                                          target_dataset, transport, ssh_credentials)

    @private
    def new_snapshot_name(self, naming_schema):
        return datetime.now().strftime(naming_schema)

    # Legacy pair support
    @private
    @accepts(Dict(
        "replication-pair-data",
        Str("hostname", required=True),
        Str("public-key", required=True),
        Str("user", null=True),
    ))
    async def pair(self, data):
        result = await self.middleware.call("keychaincredential.ssh_pair", {
            "remote_hostname": data["hostname"],
            "username": data["user"] or "root",
            "public_key": data["public-key"],
        })
        return {
            "ssh_port": result["port"],
            "ssh_hostkey": result["host_key"],
        }


class ReplicationFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'replication'
    title = 'Replication'

    async def query(self, path, enabled, options=None):
        results = []
        for replication in await self.middleware.call('replication.query', [['enabled', '=', enabled]]):
            if replication['direction'] == 'PUSH':
                if any(is_child(os.path.join('/mnt', source_dataset), path)
                       for source_dataset in replication['source_datasets']):
                    results.append(replication)

            if replication['direction'] == 'PULL':
                if is_child(os.path.join('/mnt', replication['target_dataset']), path):
                    results.append(replication)

        return results

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'storage.replication', attachment['id'])

        await self.middleware.call('zettarepl.update_tasks')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'storage.replication', attachment['id'],
                                       {'repl_enabled': enabled})

        await self.middleware.call('zettarepl.update_tasks')


async def on_zettarepl_state_changed(middleware, id, fields):
    if id.startswith('replication_task_'):
        task_id = int(id.split('_')[-1])
        middleware.send_event('replication.query', 'CHANGED', id=task_id, fields={'state': fields})


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', ReplicationFSAttachmentDelegate(middleware))
    await middleware.call('network.general.register_activity', 'replication', 'Replication')

    middleware.register_hook('zettarepl.state_change', on_zettarepl_state_changed)
