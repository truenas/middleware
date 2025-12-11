from datetime import datetime, time
import os
import re

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    ReplicationEntry,
    ReplicationCreateArgs, ReplicationCreateResult,
    ReplicationUpdateArgs, ReplicationUpdateResult,
    ReplicationDeleteArgs, ReplicationDeleteResult,
    ReplicationRunArgs, ReplicationRunResult,
    ReplicationRunOnetimeArgs, ReplicationRunOnetimeResult,
    ReplicationListDatasetsArgs, ReplicationListDatasetsResult,
    ReplicationCreateDatasetArgs, ReplicationCreateDatasetResult,
    ReplicationListNamingSchemasArgs, ReplicationListNamingSchemasResult,
    ReplicationCountEligibleManualSnapshotsArgs, ReplicationCountEligibleManualSnapshotsResult,
    ReplicationTargetUnmatchedSnapshotsArgs, ReplicationTargetUnmatchedSnapshotsResult,
)
from middlewared.auth import fake_app
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.service import job, private, CallError, CRUDService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.path import is_child


class ReplicationModel(sa.Model):
    __tablename__ = "storage_replication"

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
    repl_ssh_credentials_id = sa.Column(sa.ForeignKey("system_keychaincredential.id"), index=True, nullable=True)
    repl_sudo = sa.Column(sa.Boolean())
    repl_netcat_active_side = sa.Column(sa.String(120), nullable=True, default=None)
    repl_netcat_active_side_port_min = sa.Column(sa.Integer(), nullable=True)
    repl_netcat_active_side_port_max = sa.Column(sa.Integer(), nullable=True)
    repl_source_datasets = sa.Column(sa.JSON(list))
    repl_exclude = sa.Column(sa.JSON(list))
    repl_naming_schema = sa.Column(sa.JSON(list))
    repl_name_regex = sa.Column(sa.String(120), nullable=True)
    repl_auto = sa.Column(sa.Boolean(), default=True)
    repl_schedule_minute = sa.Column(sa.String(100), nullable=True, default="00")
    repl_schedule_hour = sa.Column(sa.String(100), nullable=True, default="*")
    repl_schedule_daymonth = sa.Column(sa.String(100), nullable=True, default="*")
    repl_schedule_month = sa.Column(sa.String(100), nullable=True, default="*")
    repl_schedule_dayweek = sa.Column(sa.String(100), nullable=True, default="*")
    repl_only_matching_schedule = sa.Column(sa.Boolean())
    repl_readonly = sa.Column(sa.String(120))
    repl_allow_from_scratch = sa.Column(sa.Boolean())
    repl_hold_pending_snapshots = sa.Column(sa.Boolean())
    repl_retention_policy = sa.Column(sa.String(120), default="NONE")
    repl_lifetime_unit = sa.Column(sa.String(120), nullable=True, default="WEEK")
    repl_lifetime_value = sa.Column(sa.Integer(), nullable=True, default=2)
    repl_lifetimes = sa.Column(sa.JSON(list))
    repl_large_block = sa.Column(sa.Boolean(), default=True)
    repl_embed = sa.Column(sa.Boolean(), default=False)
    repl_compressed = sa.Column(sa.Boolean(), default=True)
    repl_retries = sa.Column(sa.Integer(), default=5)
    repl_restrict_schedule_minute = sa.Column(sa.String(100), nullable=True, default="00")
    repl_restrict_schedule_hour = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_daymonth = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_month = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_dayweek = sa.Column(sa.String(100), nullable=True, default="*")
    repl_restrict_schedule_begin = sa.Column(sa.Time(), nullable=True, default=time(hour=0))
    repl_restrict_schedule_end = sa.Column(sa.Time(), nullable=True, default=time(hour=23, minute=45))
    repl_netcat_active_side_listen_address = sa.Column(sa.String(120), nullable=True, default=None)
    repl_netcat_passive_side_connect_address = sa.Column(sa.String(120), nullable=True, default=None)
    repl_logging_level = sa.Column(sa.String(120), nullable=True, default=None)
    repl_name = sa.Column(sa.String(120))
    repl_state = sa.Column(sa.Text(), default="{}")
    repl_properties = sa.Column(sa.Boolean(), default=True)
    repl_properties_exclude = sa.Column(sa.JSON(list))
    repl_properties_override = sa.Column(sa.JSON())
    repl_replicate = sa.Column(sa.Boolean())
    repl_encryption = sa.Column(sa.Boolean())
    repl_encryption_inherit = sa.Column(sa.Boolean(), nullable=True)
    repl_encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    repl_encryption_key_format = sa.Column(sa.String(120), nullable=True)
    repl_encryption_key_location = sa.Column(sa.Text(), nullable=True)

    repl_periodic_snapshot_tasks = sa.relationship("PeriodicSnapshotTaskModel",
                                                   secondary=lambda: ReplicationPeriodicSnapshotTaskModel.__table__)


class ReplicationPeriodicSnapshotTaskModel(sa.Model):
    __tablename__ = "storage_replication_repl_periodic_snapshot_tasks"

    id = sa.Column(sa.Integer(), primary_key=True)
    replication_id = sa.Column(sa.ForeignKey("storage_replication.id", ondelete="CASCADE"), index=True)
    task_id = sa.Column(sa.ForeignKey("storage_task.id", ondelete="CASCADE"), index=True)


class ReplicationPairArgs(BaseModel):
    hostname: str
    public_key: str = Field(alias="public-key")
    user: str | None


class ReplicationPairResult(BaseModel):
    result: dict


class ReplicationService(CRUDService):

    class Config:
        datastore = "storage.replication"
        datastore_prefix = "repl_"
        datastore_extend = "replication.extend"
        datastore_extend_context = "replication.extend_context"
        cli_namespace = "task.replication"
        entry = ReplicationEntry
        role_prefix = "REPLICATION_TASK"

    @private
    async def extend_context(self, rows, extra):
        if extra.get("check_dataset_encryption_keys", False) and any(row["direction"] == "PUSH" for row in rows):
            dataset_mapping = await self.middleware.call("pool.dataset.dataset_encryption_root_mapping")
        else:
            dataset_mapping = {}

        return {
            "state": await self.middleware.call("zettarepl.get_state"),
            "dataset_encryption_root_mapping": dataset_mapping,
            "check_dataset_encryption_keys": extra.get("check_dataset_encryption_keys", False),
        }

    @private
    async def extend(self, data, context):
        data["periodic_snapshot_tasks"] = [
            {k.replace("task_", ""): v for k, v in task.items()}
            for task in data["periodic_snapshot_tasks"]
        ]

        for task in data["periodic_snapshot_tasks"]:
            convert_db_format_to_schedule(task, begin_end=True)

        if data["direction"] == "PUSH":
            data["also_include_naming_schema"] = data["naming_schema"]
            data["naming_schema"] = []
        if data["direction"] == "PULL":
            data["also_include_naming_schema"] = []

        convert_db_format_to_schedule(data, "schedule", key_prefix="schedule_", begin_end=True)
        convert_db_format_to_schedule(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        if "error" in context["state"]:
            data["state"] = context["state"]["error"]
        else:
            data["state"] = context["state"]["tasks"].get(f"replication_task_{data['id']}", {
                "state": "PENDING",
            })

        data["job"] = data["state"].pop("job", None)

        data["has_encrypted_dataset_keys"] = False
        if context["check_dataset_encryption_keys"]:
            if context["dataset_encryption_root_mapping"] and data["direction"] == "PUSH":
                data["has_encrypted_dataset_keys"] = bool(
                    await self.middleware.call(
                        "pool.dataset.export_keys_for_replication_internal", data,
                        context["dataset_encryption_root_mapping"], True,
                    )
                )

        return data

    @private
    async def compress(self, data):
        if data["direction"] == "PUSH":
            data["naming_schema"] = data["also_include_naming_schema"]
        del data["also_include_naming_schema"]

        convert_schedule_to_db_format(data, "schedule", key_prefix="schedule_", begin_end=True)
        convert_schedule_to_db_format(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        del data["periodic_snapshot_tasks"]

        return data

    @api_method(
        ReplicationCreateArgs,
        ReplicationCreateResult,
        audit="Replication task create:",
        audit_extended=lambda data: data["name"],
        pass_app=True,
        pass_app_require=True,
    )
    async def do_create(self, app, data):
        """
        Create a Replication Task that will push or pull ZFS snapshots to or from remote host.
        """

        verrors = ValidationErrors()
        verrors.add_child("replication_create", await self._validate(app, data))

        verrors.check()

        periodic_snapshot_tasks = data["periodic_snapshot_tasks"]
        await self.compress(data)

        id_ = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data,
            {"prefix": self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id_, periodic_snapshot_tasks)

        await self.middleware.call("zettarepl.update_tasks")

        return await self.get_instance(id_)

    @api_method(
        ReplicationUpdateArgs,
        ReplicationUpdateResult,
        audit="Replication task update:",
        audit_callback=True,
        pass_app=True,
        pass_app_require=True,
    )
    async def do_update(self, app, audit_callback, id_, data):
        """
        Update a Replication Task with specific `id`.
        """

        old = await self.get_instance(id_)
        audit_callback(old["name"])

        new = old.copy()
        if new["ssh_credentials"]:
            new["ssh_credentials"] = new["ssh_credentials"]["id"]
        new["periodic_snapshot_tasks"] = [task["id"] for task in new["periodic_snapshot_tasks"]]
        new.update(data)

        verrors = ValidationErrors()
        verrors.add_child("replication_update", await self._validate(app, new, id_))

        verrors.check()

        periodic_snapshot_tasks = new["periodic_snapshot_tasks"]
        await self.compress(new)

        new.pop("state", None)
        new.pop("job", None)
        new.pop("has_encrypted_dataset_keys", None)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
            {"prefix": self._config.datastore_prefix}
        )

        await self._set_periodic_snapshot_tasks(id_, periodic_snapshot_tasks)

        await self.middleware.call("zettarepl.update_tasks")

        return await self.get_instance(id_)

    @api_method(
        ReplicationDeleteArgs,
        ReplicationDeleteResult,
        audit="Replication task delete:",
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete a Replication Task with specific `id`
        """
        task_name = (await self.get_instance(id_))["name"]
        audit_callback(task_name)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        await self.middleware.call("zettarepl.update_tasks")

        return response

    @api_method(
        ReplicationRunArgs,
        ReplicationRunResult,
        roles=["REPLICATION_TASK_WRITE"],
    )
    @job(logs=True, read_roles=["REPLICATION_TASK_READ"])
    async def run(self, job, id_, really_run):
        """
        Run Replication Task of `id`.
        """
        if really_run:
            task = await self.get_instance(id_)

            if not task["enabled"]:
                raise CallError("Task is not enabled")

            if task["state"]["state"] == "RUNNING":
                raise CallError("Task is already running")

            if task["state"]["state"] == "HOLD":
                raise CallError("Task is on hold")

        await self.middleware.call("zettarepl.run_replication_task", id_, really_run, job)

    @api_method(ReplicationRunOnetimeArgs, ReplicationRunOnetimeResult, roles=["REPLICATION_TASK_WRITE"])
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
        verrors.add_child("replication_run_onetime", await self._validate(fake_app(), data))

        verrors.check()

        if data.get("ssh_credentials") is not None:
            data["ssh_credentials"] = await self.middleware.call(
                "keychaincredential.get_of_type", data["ssh_credentials"], "SSH_CREDENTIALS",
            )

        await self.middleware.call("zettarepl.run_onetime_replication_task", job, data)

    async def _validate(self, app, data, id_=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, "", "name", data["name"], id_)

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

            if app.authenticated_credentials.has_role("REPLICATION_TASK_WRITE"):
                if not app.authenticated_credentials.has_role("REPLICATION_TASK_WRITE_PULL"):
                    verrors.add("direction", "You don't have permissions to use PULL replication")

        # Transport

        if data["transport"] == "SSH+NETCAT":
            if data["netcat_active_side"] is None:
                verrors.add("netcat_active_side", "You must choose active side for SSH+netcat replication")

            if data["netcat_active_side_port_min"] is not None and data["netcat_active_side_port_max"] is not None:
                if data["netcat_active_side_port_min"] > data["netcat_active_side_port_max"]:
                    verrors.add("netcat_active_side_port_max",
                                "Please specify value greater than or equal to netcat_active_side_port_min")

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

            if data["retention_policy"] != "SOURCE":
                verrors.add(
                    "retention_policy",
                    "Only `Same as Source` retention policy can be used for full filesystem replication",
                )

            for i, source_dataset in enumerate(data["source_datasets"]):
                for j, another_source_dataset in enumerate(data["source_datasets"]):
                    if j != i:
                        if is_child(source_dataset, another_source_dataset):
                            verrors.add(
                                f"source_datasets.{i}",
                                "Replication task that replicates the entire filesystem can't replicate both "
                                f"{another_source_dataset!r} and its child {source_dataset!r}"
                            )

            for i, periodic_snapshot_task in enumerate(snapshot_tasks):
                if (
                    not any(is_child(source_dataset, periodic_snapshot_task["dataset"])
                            for source_dataset in data["source_datasets"]) or
                    not periodic_snapshot_task["recursive"]
                ):
                    verrors.add(
                        f"periodic_snapshot_tasks.{i}",
                        "Replication tasks that replicate the entire filesystem can only use periodic snapshot tasks "
                        "that take recursive snapshots of the dataset being replicated (or its ancestor)"
                    )

        if data["encryption"]:
            if not data["encryption_inherit"]:
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

            if snapshot_tasks:
                verrors.add("name_regex", "Naming regex can't be used with periodic snapshot tasks")

            if data["naming_schema"] or data["also_include_naming_schema"]:
                verrors.add("name_regex", "Naming regex can't be used with Naming schema")

            if data["retention_policy"] not in ["SOURCE", "NONE"]:
                verrors.add(
                    "retention_policy",
                    "Only `Same as Source` and `None` retention policies can be used with Naming regex",
                )

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

    @api_method(ReplicationListDatasetsArgs, ReplicationListDatasetsResult, roles=["REPLICATION_TASK_WRITE"])
    async def list_datasets(self, transport, ssh_credentials):
        """
        List datasets on remote side
        """

        return await self.middleware.call("zettarepl.list_datasets", transport, ssh_credentials)

    @api_method(ReplicationCreateDatasetArgs, ReplicationCreateDatasetResult, roles=["REPLICATION_TASK_WRITE"])
    async def create_dataset(self, dataset, transport, ssh_credentials):
        """
        Creates dataset on remote side
        """
        return await self.middleware.call("zettarepl.create_dataset", dataset, transport, ssh_credentials)

    @api_method(ReplicationListNamingSchemasArgs, ReplicationListNamingSchemasResult, roles=["REPLICATION_TASK_WRITE"])
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

    @api_method(
        ReplicationCountEligibleManualSnapshotsArgs,
        ReplicationCountEligibleManualSnapshotsResult,
        roles=["REPLICATION_TASK_WRITE"],
    )
    async def count_eligible_manual_snapshots(self, data):
        """
        Count how many existing snapshots of `dataset` match `naming_schema`.
        """
        return await self.middleware.call("zettarepl.count_eligible_manual_snapshots", data)

    @api_method(
        ReplicationTargetUnmatchedSnapshotsArgs,
        ReplicationTargetUnmatchedSnapshotsResult,
        roles=["REPLICATION_TASK_WRITE"],
    )
    async def target_unmatched_snapshots(self, direction, source_datasets, target_dataset, transport, ssh_credentials):
        """
        Check if target has any snapshots that do not exist on source. Returns these snapshots grouped by dataset.
        """
        return await self.middleware.call("zettarepl.target_unmatched_snapshots", direction, source_datasets,
                                          target_dataset, transport, ssh_credentials)

    @private
    def new_snapshot_name(self, naming_schema):
        return datetime.now().strftime(naming_schema)

    # Legacy pair support
    @api_method(ReplicationPairArgs, ReplicationPairResult, private=True)
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
    name = "replication"
    title = "Replication"

    async def query(self, path, enabled, options=None):
        results = []
        for replication in await self.middleware.call("replication.query", [["enabled", "=", enabled]]):
            if replication["transport"] == "LOCAL" or replication["direction"] == "PUSH":
                if await self.middleware.call("filesystem.is_child", [
                    os.path.join("/mnt", source_dataset) for source_dataset in replication["source_datasets"]
                ], path):
                    results.append(replication)

            if replication["transport"] == "LOCAL" or replication["direction"] == "PULL":
                if await self.middleware.call(
                    "filesystem.is_child",
                    os.path.join("/mnt", replication["target_dataset"]),
                    path
                ):
                    results.append(replication)

        return results

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call("datastore.delete", "storage.replication", attachment["id"])

        await self.middleware.call("zettarepl.update_tasks")

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call("datastore.update", "storage.replication", attachment["id"],
                                       {"repl_enabled": enabled})

        await self.middleware.call("zettarepl.update_tasks")


async def on_zettarepl_state_changed(middleware, id_, fields):
    if id_.startswith("replication_task_"):
        task_id = int(id_.split("_")[-1])
        middleware.send_event("replication.query", "CHANGED", id=task_id, fields={"state": fields})


async def setup(middleware):
    await middleware.call("pool.dataset.register_attachment_delegate", ReplicationFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "replication", "Replication")

    middleware.register_hook("zettarepl.state_change", on_zettarepl_state_changed)
