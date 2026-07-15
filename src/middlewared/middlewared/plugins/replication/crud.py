from __future__ import annotations

from datetime import time
import re
from typing import TYPE_CHECKING, Any

from middlewared.api.current import (
    PeriodicSnapshotTaskEntry,
    ReplicationCreate,
    ReplicationEntry,
    ReplicationRunOnetimeArgs,
    ReplicationUpdate,
)
from middlewared.auth import fake_app
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.path import is_child

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.auth import FakeApplication
    from middlewared.job import Job
    from middlewared.utils.types import AuditCallback


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
    repl_properties_override = sa.Column(sa.JSON(dict))
    repl_replicate = sa.Column(sa.Boolean())
    repl_encryption = sa.Column(sa.Boolean())
    repl_encryption_inherit = sa.Column(sa.Boolean(), nullable=True)
    repl_encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    repl_encryption_key_format = sa.Column(sa.String(120), nullable=True)
    repl_encryption_key_location = sa.Column(sa.Text(), nullable=True)

    repl_periodic_snapshot_tasks = sa.relationship(
        "PeriodicSnapshotTaskModel", secondary=lambda: ReplicationPeriodicSnapshotTaskModel.__table__
    )


class ReplicationPeriodicSnapshotTaskModel(sa.Model):
    __tablename__ = "storage_replication_repl_periodic_snapshot_tasks"

    id = sa.Column(sa.Integer(), primary_key=True)
    replication_id = sa.Column(sa.ForeignKey("storage_replication.id", ondelete="CASCADE"), index=True)
    task_id = sa.Column(sa.ForeignKey("storage_task.id", ondelete="CASCADE"), index=True)


class ReplicationServicePart(CRUDServicePart[ReplicationEntry]):
    _datastore = "storage.replication"
    _datastore_prefix = "repl_"
    _entry = ReplicationEntry

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        if extra.get("check_dataset_encryption_keys", False) and any(row["direction"] == "PUSH" for row in rows):
            dataset_mapping = await self.middleware.call("pool.dataset.dataset_encryption_root_mapping")
        else:
            dataset_mapping = {}

        return {
            "state": await self.middleware.call("zettarepl.get_state"),
            "dataset_encryption_root_mapping": dataset_mapping,
            "check_dataset_encryption_keys": extra.get("check_dataset_encryption_keys", False),
        }

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data["periodic_snapshot_tasks"] = [
            {k.replace("task_", ""): v for k, v in task.items()} for task in data["periodic_snapshot_tasks"]
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
            data["state"] = context["state"]["tasks"].get(
                f"replication_task_{data['id']}",
                {
                    "state": "PENDING",
                },
            )

        data["job"] = data["state"].pop("job", None)

        data["has_encrypted_dataset_keys"] = False
        if context["check_dataset_encryption_keys"]:
            if context["dataset_encryption_root_mapping"] and data["direction"] == "PUSH":
                data["has_encrypted_dataset_keys"] = bool(
                    await self.middleware.call(
                        "pool.dataset.export_keys_for_replication_internal",
                        self._to_entry(data),
                        context["dataset_encryption_root_mapping"],
                        True,
                    )
                )

        return data

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["direction"] == "PUSH":
            data["naming_schema"] = data["also_include_naming_schema"]
        del data["also_include_naming_schema"]

        convert_schedule_to_db_format(data, "schedule", key_prefix="schedule_", begin_end=True)
        convert_schedule_to_db_format(data, "restrict_schedule", key_prefix="restrict_schedule_", begin_end=True)

        del data["periodic_snapshot_tasks"]

        return data

    async def do_create(self, app: App, data: ReplicationCreate) -> ReplicationEntry:
        verrors = ValidationErrors()
        verrors.add_child("replication_create", await self.validate(app, data))
        verrors.check()

        ds = data.model_dump()
        periodic_snapshot_tasks = ds["periodic_snapshot_tasks"]
        self.compress(ds)

        id_ = await self.middleware.call(
            "datastore.insert",
            self._datastore,
            ds,
            {"prefix": self._datastore_prefix},
        )

        await self._set_periodic_snapshot_tasks(id_, periodic_snapshot_tasks)

        await self.middleware.call("zettarepl.update_tasks")

        return await self.get_instance(id_)

    async def do_update(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
        data: ReplicationUpdate,
    ) -> ReplicationEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        # Reduce the current entry to a `ReplicationCreate` shape (`ssh_credentials` and
        # `periodic_snapshot_tasks` as ids), then apply the requested changes on top of it.
        current = ReplicationCreate(
            **old.model_dump(
                exclude={
                    "id",
                    "state",
                    "job",
                    "has_encrypted_dataset_keys",
                    "ssh_credentials",
                    "periodic_snapshot_tasks",
                },
            ),
            ssh_credentials=old.ssh_credentials.id if old.ssh_credentials else None,
            periodic_snapshot_tasks=[task.id for task in old.periodic_snapshot_tasks],
        )
        new = current.updated(data)

        verrors = ValidationErrors()
        verrors.add_child("replication_update", await self.validate(app, new, id_))
        verrors.check()

        ds = new.model_dump()
        periodic_snapshot_tasks = ds["periodic_snapshot_tasks"]
        self.compress(ds)

        await self.middleware.call(
            "datastore.update",
            self._datastore,
            id_,
            ds,
            {"prefix": self._datastore_prefix},
        )

        await self._set_periodic_snapshot_tasks(id_, periodic_snapshot_tasks)

        await self.middleware.call("zettarepl.update_tasks")

        return await self.get_instance(id_)

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> bool:
        task_name = (await self.get_instance(id_)).name
        audit_callback(task_name)

        response: bool = await self.middleware.call("datastore.delete", self._datastore, id_)

        # Remove task state from zettarepl before updating tasks
        await self.middleware.call("zettarepl.remove_task", f"replication_task_{id_}")

        await self.middleware.call("zettarepl.update_tasks")

        return response

    async def _set_periodic_snapshot_tasks(
        self,
        replication_task_id: int,
        periodic_snapshot_tasks_ids: list[int],
    ) -> None:
        await self.middleware.call(
            "datastore.delete",
            "storage.replication_repl_periodic_snapshot_tasks",
            [["replication_id", "=", replication_task_id]],
        )
        for periodic_snapshot_task_id in periodic_snapshot_tasks_ids:
            await self.middleware.call(
                "datastore.insert",
                "storage.replication_repl_periodic_snapshot_tasks",
                {
                    "replication_id": replication_task_id,
                    "task_id": periodic_snapshot_task_id,
                },
            )

    async def run_onetime(self, job: Job, data: ReplicationRunOnetimeArgs) -> None:
        payload = data.model_dump()
        payload["name"] = f"Temporary replication task for job {job.id}"
        payload["schedule"] = None
        payload["only_matching_schedule"] = False
        payload["auto"] = False
        payload["enabled"] = True

        # `payload` carries every `ReplicationCreate` field (plus one-time-only extras like `mount`); pick out
        # exactly the `ReplicationCreate` fields so it can be validated as a model.
        replication_create = ReplicationCreate(
            **{k: payload[k] for k in ReplicationCreate.model_fields if k in payload}
        )
        verrors = ValidationErrors()
        verrors.add_child("replication_run_onetime", await self.validate(fake_app(), replication_create))
        verrors.check()

        if payload.get("ssh_credentials") is not None:
            ssh_credentials = await self.call2(
                self.s.keychaincredential.get_of_type,
                payload["ssh_credentials"],
                "SSH_CREDENTIALS",
            )
            payload["ssh_credentials"] = ssh_credentials.model_dump(context={"expose_secrets": True})

        await self.middleware.call("zettarepl.run_onetime_replication_task", job, payload)

    async def validate(
        self,
        app: App | FakeApplication,
        data: ReplicationCreate,
        id_: int | None = None,
    ) -> ValidationErrors:
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, "", "name", data.name, id_)

        # Direction
        snapshot_tasks = await self._validate_direction(app.authenticated_credentials, data, verrors)

        # Transport
        await self._validate_transport(data, verrors)

        # Common for all directions and transports
        self._validate_source_datasets(data, snapshot_tasks, verrors)
        self._validate_common(data, snapshot_tasks, verrors)

        return verrors

    async def _validate_direction(
        self,
        app_creds: Any,
        data: ReplicationCreate,
        verrors: ValidationErrors,
    ) -> list[PeriodicSnapshotTaskEntry]:
        """
        Validate direction-specific settings (PUSH vs PULL).
        Returns list of periodic snapshot tasks (empty for PULL).
        """
        periodic_snapshot_tasks = data.periodic_snapshot_tasks
        naming_schema = data.naming_schema
        also_include_naming_schema = data.also_include_naming_schema
        name_regex = data.name_regex
        schedule = data.schedule
        auto = data.auto
        snapshot_tasks: list[PeriodicSnapshotTaskEntry] = []

        match data.direction:
            case "PUSH":
                # Query and validate periodic snapshot tasks
                e, snapshot_tasks = await self._query_periodic_snapshot_tasks(periodic_snapshot_tasks)
                verrors.add_child("periodic_snapshot_tasks", e)

                # PUSH gets snapshot names from tasks, not from naming_schema
                if naming_schema:
                    verrors.add("naming_schema", "This field has no sense for push replication")

                # PUSH needs at least one way to identify snapshots to replicate
                if not snapshot_tasks and not also_include_naming_schema and not name_regex:
                    verrors.add(
                        "periodic_snapshot_tasks",
                        'You must at least either bind a periodic snapshot task or provide "Also Include Naming '
                        'Schema" or "Name Regex" for push replication task',
                    )

                # Automatic PUSH needs a trigger (schedule or periodic snapshot task)
                if schedule is None and auto and not periodic_snapshot_tasks:
                    verrors.add(
                        "auto",
                        "Push replication that runs automatically must be either bound to a periodic snapshot task or "
                        "have a schedule",
                    )

            case "PULL":
                # PULL always needs a schedule since we don't control the remote snapshot creation
                if schedule is None and auto:
                    verrors.add("auto", "Pull replication that runs automatically must have a schedule")

                # PULL can't use periodic snapshot tasks (they're for local snapshots only)
                if periodic_snapshot_tasks:
                    verrors.add(
                        "periodic_snapshot_tasks", "Pull replication can't be bound to a periodic snapshot task"
                    )

                # PULL needs naming_schema or name_regex to identify remote snapshots
                if not naming_schema and not name_regex:
                    verrors.add("naming_schema", "Naming schema or Name regex are required for pull replication")

                # also_include_naming_schema only makes sense with periodic snapshot tasks
                if also_include_naming_schema:
                    verrors.add("also_include_naming_schema", "This field has no sense for pull replication")

                # PULL can't hold snapshots on source (we don't have access to do retention there)
                if data.hold_pending_snapshots:
                    verrors.add(
                        "hold_pending_snapshots",
                        "Pull replication tasks can't hold pending snapshots because they don't do source retention",
                    )

                # PULL replication requires explicit permission (security: pulling data from remote)
                if app_creds.has_role("REPLICATION_TASK_WRITE") and not app_creds.has_role(
                    "REPLICATION_TASK_WRITE_PULL"
                ):
                    verrors.add("direction", "You don't have permissions to use PULL replication")

        return snapshot_tasks

    async def _validate_transport(self, data: ReplicationCreate, verrors: ValidationErrors) -> None:
        """Validate transport settings (SSH+NETCAT, LOCAL, or SSH)."""
        transport = data.transport
        netcat_active_side = data.netcat_active_side
        compression = data.compression
        speed_limit = data.speed_limit

        # SSH+NETCAT: Uses SSH for control, netcat for data transfer
        if transport == "SSH+NETCAT":
            # Must specify which side opens the netcat listener
            if netcat_active_side is None:
                verrors.add("netcat_active_side", "You must choose active side for SSH+netcat replication")

            # Validate port range for netcat listener
            port_min = data.netcat_active_side_port_min
            port_max = data.netcat_active_side_port_max
            if port_min is not None and port_max is not None and port_min > port_max:
                verrors.add(
                    "netcat_active_side_port_max",
                    "Please specify value greater than or equal to netcat_active_side_port_min",
                )

            # Netcat handles raw data transfer, so compression/speed limit not applicable
            if compression is not None:
                verrors.add("compression", "Compression is not supported for SSH+netcat replication")

            if speed_limit is not None:
                verrors.add("speed_limit", "Speed limit is not supported for SSH+netcat replication")
        else:
            # For SSH and LOCAL: Netcat-specific fields should not be set
            if netcat_active_side is not None:
                verrors.add("netcat_active_side", "This field only has sense for SSH+netcat replication")

            # Check all netcat-specific fields are null for non-netcat transports
            for k in (
                "netcat_active_side_listen_address",
                "netcat_active_side_port_min",
                "netcat_active_side_port_max",
                "netcat_passive_side_connect_address",
            ):
                if getattr(data, k) is not None:
                    verrors.add(k, "This field only has sense for SSH+netcat replication")

        # Validate credentials based on transport type
        ssh_credentials = data.ssh_credentials
        if transport == "LOCAL":
            # LOCAL replication is same-system, so no remote credentials or network features
            if ssh_credentials is not None:
                verrors.add("ssh_credentials", "Remote credentials have no sense for local replication")

            if compression is not None:
                verrors.add("compression", "Compression has no sense for local replication")

            if speed_limit is not None:
                verrors.add("speed_limit", "Speed limit has no sense for local replication")
        elif ssh_credentials is None:
            # SSH and SSH+NETCAT both require SSH credentials
            verrors.add("ssh_credentials", "SSH Credentials are required for non-local replication")
        else:
            # Verify the SSH credentials exist and are valid
            try:
                await self.call2(self.s.keychaincredential.get_of_type, ssh_credentials, "SSH_CREDENTIALS")
            except CallError as e:
                verrors.add("ssh_credentials", str(e))

    def _validate_source_datasets(
        self,
        data: ReplicationCreate,
        snapshot_tasks: list[PeriodicSnapshotTaskEntry],
        verrors: ValidationErrors,
    ) -> None:
        """Validate source datasets, exclusions, and full filesystem replication settings."""
        source_datasets = data.source_datasets
        recursive = data.recursive
        exclude = data.exclude

        # Validate that exclusions are consistent between replication task and snapshot tasks
        for i, src_ds in enumerate(source_datasets):
            for periodic_snapshot_task in snapshot_tasks:
                task_ds = periodic_snapshot_task.dataset
                if is_child(src_ds, task_ds):
                    task_exclude = periodic_snapshot_task.exclude
                    if recursive:
                        # For recursive replication, snapshot task exclusions should be replicated in our exclude list
                        for task_exclude_item in task_exclude:
                            if is_child(task_exclude_item, src_ds) and task_exclude_item not in exclude:
                                verrors.add(
                                    "exclude",
                                    f"You should exclude {task_exclude_item!r} as bound periodic snapshot task dataset "
                                    f"{task_ds!r} does",
                                )
                    elif src_ds in task_exclude:
                        # For non-recursive, can't replicate a dataset that's excluded from snapshots
                        verrors.add(
                            f"source_datasets.{i}",
                            f"Dataset {src_ds!r} is excluded by bound periodic snapshot task for dataset {task_ds!r}",
                        )

        # Exclude lists only work with recursive replication
        if not recursive and exclude:
            verrors.add("exclude", "Excluding child datasets is only supported for recursive replication")

        # Every excluded dataset must be a child of at least one source dataset
        for i, v in enumerate(exclude):
            if not any(v.startswith(ds + "/") for ds in source_datasets):
                verrors.add(f"exclude.{i}", "This dataset is not a child of any of source datasets")

        # Full filesystem replication (replicate=True) has additional requirements
        if not data.replicate:
            return

        # Full filesystem replication must include all children and properties
        required_msg = "This option is required for full filesystem replication"
        if not recursive:
            verrors.add("recursive", required_msg)

        if exclude:
            verrors.add("exclude", "This option is not supported for full filesystem replication")

        if not data.properties:
            verrors.add("properties", required_msg)

        # Full filesystem replication must use SOURCE retention to match source exactly
        if data.retention_policy != "SOURCE":
            verrors.add(
                "retention_policy",
                "Only `Same as Source` retention policy can be used for full filesystem replication",
            )

        # Source datasets can't overlap (e.g., can't replicate both tank/foo and tank/foo/bar)
        for i, src_ds in enumerate(source_datasets):
            for j, another_src_ds in enumerate(source_datasets):
                if j != i and is_child(src_ds, another_src_ds):
                    verrors.add(
                        f"source_datasets.{i}",
                        "Replication task that replicates the entire filesystem can't replicate both "
                        f"{another_src_ds!r} and its child {src_ds!r}",
                    )

        # Snapshot tasks must be recursive and cover the source datasets
        for i, periodic_snapshot_task in enumerate(snapshot_tasks):
            if (
                not any(is_child(src_ds, periodic_snapshot_task.dataset) for src_ds in source_datasets)
                or not periodic_snapshot_task.recursive
            ):
                verrors.add(
                    f"periodic_snapshot_tasks.{i}",
                    "Replication tasks that replicate the entire filesystem can only use periodic snapshot tasks "
                    "that take recursive snapshots of the dataset being replicated (or its ancestor)",
                )

    def _validate_common(
        self,
        data: ReplicationCreate,
        snapshot_tasks: list[PeriodicSnapshotTaskEntry],
        verrors: ValidationErrors,
    ) -> None:
        """Validate common settings (encryption, schedules, retention, naming)."""
        # When encryption is enabled but not inherited, must specify key details
        if data.encryption and not data.encryption_inherit:
            for k in ("encryption_key", "encryption_key_format", "encryption_key_location"):
                if getattr(data, k) is None:
                    verrors.add(k, "This property is required when remote dataset encryption is enabled")

        # Schedule validation: schedule requires auto, only_matching_schedule requires schedule
        if data.schedule:
            if not data.auto:
                verrors.add("schedule", "You can't have schedule for replication that does not run automatically")
        elif data.only_matching_schedule:
            verrors.add("only_matching_schedule", "You can't have only-matching-schedule without schedule")

        # Name regex validation and compatibility checks
        name_regex = data.name_regex
        retention_policy = data.retention_policy
        if name_regex:
            # Verify regex syntax is valid
            try:
                re.compile(f"({name_regex})$")
            except Exception as e:
                verrors.add("name_regex", f"Invalid regex: {e}")

            # Name regex is mutually exclusive with snapshot tasks (which provide their own naming)
            if snapshot_tasks:
                verrors.add("name_regex", "Naming regex can't be used with periodic snapshot tasks")

            # Name regex is mutually exclusive with naming schema
            if data.naming_schema or data.also_include_naming_schema:
                verrors.add("name_regex", "Naming regex can't be used with Naming schema")

            # Name regex has limited retention policy options (can't calculate lifetimes from arbitrary names)
            if retention_policy not in ("SOURCE", "NONE"):
                verrors.add(
                    "retention_policy",
                    "Only `Same as Source` and `None` retention policies can be used with Naming regex",
                )

        # Retention policy validation: CUSTOM requires lifetime settings, others forbid them
        lifetime_value = data.lifetime_value
        lifetime_unit = data.lifetime_unit
        if retention_policy == "CUSTOM":
            # CUSTOM retention needs both value and unit to calculate snapshot lifetime
            errmsg = "This field is required for custom retention policy"
            if lifetime_value is None:
                verrors.add("lifetime_value", errmsg)
            if lifetime_unit is None:
                verrors.add("lifetime_unit", errmsg)
        else:
            # Non-CUSTOM retention policies (SOURCE, NONE) don't use lifetime settings
            errmsg = "This field has no sense for specified retention policy"
            if lifetime_value is not None:
                verrors.add("lifetime_value", errmsg)
            if lifetime_unit is not None:
                verrors.add("lifetime_unit", errmsg)
            if data.lifetimes:
                verrors.add("lifetimes", errmsg)

        # Can't bind disabled snapshot tasks to enabled replication tasks
        if not data.enabled:
            return

        for i, snapshot_task in enumerate(snapshot_tasks):
            if not snapshot_task.enabled:
                verrors.add(
                    f"periodic_snapshot_tasks.{i}",
                    "You can't bind disabled periodic snapshot task to enabled replication task",
                )

    async def _query_periodic_snapshot_tasks(
        self,
        ids: list[int],
    ) -> tuple[ValidationErrors, list[PeriodicSnapshotTaskEntry]]:
        verrors = ValidationErrors()

        query_result = await self.call2(self.s.pool.snapshottask.query, [["id", "in", ids]])

        snapshot_tasks = []
        for i, task_id in enumerate(ids):
            for task in query_result:
                if task.id == task_id:
                    snapshot_tasks.append(task)
                    break
            else:
                verrors.add(str(i), "This snapshot task does not exist")

        return verrors, snapshot_tasks
