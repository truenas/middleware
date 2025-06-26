from typing import Literal

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
                                  single_argument_args, single_argument_result, SnapshotNameSchema, TcpPort,
                                  UniqueList)
from .common import CronModel, TimeCronModel
from .keychain import KeychainCredentialEntry
from .pool_snapshottask import PoolSnapshotTaskDBEntry

__all__ = ["ReplicationEntry",
           "ReplicationCreateArgs", "ReplicationCreateResult",
           "ReplicationUpdateArgs", "ReplicationUpdateResult",
           "ReplicationDeleteArgs", "ReplicationDeleteResult",
           "ReplicationRunArgs", "ReplicationRunResult",
           "ReplicationRunOnetimeArgs", "ReplicationRunOnetimeResult",
           "ReplicationListDatasetsArgs", "ReplicationListDatasetsResult",
           "ReplicationCreateDatasetArgs", "ReplicationCreateDatasetResult",
           "ReplicationListNamingSchemasArgs", "ReplicationListNamingSchemasResult",
           "ReplicationCountEligibleManualSnapshotsArgs", "ReplicationCountEligibleManualSnapshotsResult",
           "ReplicationTargetUnmatchedSnapshotsArgs", "ReplicationTargetUnmatchedSnapshotsResult"]


class ReplicationTimeCronModel(TimeCronModel):
    minute: str = "00"


class ReplicationLifetimeModel(BaseModel):
    schedule: CronModel
    lifetime_value: int = Field(ge=1)
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]


class ReplicationEntry(BaseModel):
    id: int
    name: NonEmptyString
    """Name for replication task."""
    direction: Literal["PUSH", "PULL"]
    """Whether task will `PUSH` or `PULL` snapshots."""
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    """
    Method of snapshots transfer.

    * `SSH` transfers snapshots via SSH connection. This method is supported everywhere but does not achieve \
      great performance.
    * `SSH+NETCAT` uses unencrypted connection for data transfer. This can only be used in trusted networks \
      and requires a port (specified by range from `netcat_active_side_port_min` to `netcat_active_side_port_max`) \
      to be open on `netcat_active_side`.
    * `LOCAL` replicates to or from localhost.
    """
    ssh_credentials: KeychainCredentialEntry | None = None
    """Keychain Credential of type `SSH_CREDENTIALS`."""
    netcat_active_side: Literal["LOCAL", "REMOTE"] | None = None
    netcat_active_side_listen_address: str | None = None
    netcat_active_side_port_min: TcpPort | None = None
    netcat_active_side_port_max: TcpPort | None = None
    netcat_passive_side_connect_address: str | None = None
    sudo: bool = False
    """`SSH` and `SSH+NETCAT` transports should use sudo (which is expected to be passwordless) to run `zfs` \
    command on the remote machine."""
    source_datasets: list[str] = Field(min_items=1)
    """List of datasets to replicate snapshots from."""
    target_dataset: str
    """Dataset to put snapshots into."""
    recursive: bool
    exclude: list[str] = []
    properties: bool = True
    """Send dataset properties along with snapshots."""
    properties_exclude: list[NonEmptyString] = []
    properties_override: dict[str, str] = {}
    replicate: bool = False
    encryption: bool = False
    encryption_inherit: bool | None = None
    encryption_key: str | None = None
    encryption_key_format: Literal["HEX", "PASSPHRASE"] | None = None
    encryption_key_location: str | None = None
    periodic_snapshot_tasks: list[PoolSnapshotTaskDBEntry]
    """List of periodic snapshot tasks that are sources of snapshots for this replication task. Only push replication \
    tasks can be bound to periodic snapshot tasks."""
    naming_schema: list[SnapshotNameSchema] = []
    """List of naming schemas for pull replication."""
    also_include_naming_schema: list[SnapshotNameSchema] = []
    """List of naming schemas for push replication."""
    name_regex: NonEmptyString | None = None
    """Replicate all snapshots which names match specified regular expression."""
    auto: bool
    """Allow replication to run automatically on schedule or after bound periodic snapshot task."""
    schedule: ReplicationTimeCronModel | None = None
    """Schedule to run replication task. Only `auto` replication tasks without bound periodic snapshot tasks can have \
    a schedule."""
    restrict_schedule: ReplicationTimeCronModel | None = None
    """Restricts when replication task with bound periodic snapshot tasks runs. For example, you can have periodic \
    snapshot tasks that run every 15 minutes, but only run replication task every hour."""
    only_matching_schedule: bool = False
    """Will only replicate snapshots that match `schedule` or `restrict_schedule`."""
    allow_from_scratch: bool = False
    """Will destroy all snapshots on target side and replicate everything from scratch if none of the snapshots on \
    target side matches source snapshots."""
    readonly: Literal["SET", "REQUIRE", "IGNORE"] = "SET"
    """
    Controls destination datasets readonly property.

    * `SET`: Set all destination datasets to readonly=on after finishing the replication.
    * `REQUIRE`: Require all existing destination datasets to have readonly=on property.
    * `IGNORE`: Avoid this kind of behavior.
    """
    hold_pending_snapshots: bool = False
    """Prevent source snapshots from being deleted by retention of replication fails for some reason."""
    retention_policy: Literal["SOURCE", "CUSTOM", "NONE"]
    """
    How to delete old snapshots on target side:

    * `SOURCE`: Delete snapshots that are absent on source side.
    * `CUSTOM`: Delete snapshots that are older than `lifetime_value` and `lifetime_unit`.
    * `NONE`: Do not delete any snapshots.
    """
    lifetime_value: int | None = Field(default=None, ge=1)
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"] | None = None
    lifetimes: list[ReplicationLifetimeModel] = []
    compression: Literal["LZ4", "PIGZ", "PLZIP"] | None = None
    """Compresses SSH stream. Available only for SSH transport."""
    speed_limit: int | None = Field(default=None, ge=1)
    """Limits speed of SSH stream. Available only for SSH transport."""
    large_block: bool = True
    embed: bool = False
    compressed: bool = True
    retries: int = Field(default=5, ge=1)
    """Number of retries before considering replication failed."""
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None
    enabled: bool = True
    state: dict
    job: dict | None
    has_encrypted_dataset_keys: bool


class ReplicationCreate(ReplicationEntry):
    id: Excluded = excluded_field()
    ssh_credentials: int | None = None
    """Keychain Credential ID of type `SSH_CREDENTIALS`."""
    periodic_snapshot_tasks: UniqueList[int] = []
    """List of periodic snapshot task IDs that are sources of snapshots for this replication task. Only push \
    replication tasks can be bound to periodic snapshot tasks."""
    state: Excluded = excluded_field()
    job: Excluded = excluded_field()
    has_encrypted_dataset_keys: Excluded = excluded_field()


class ReplicationCreateArgs(BaseModel):
    replication_create: ReplicationCreate


class ReplicationCreateResult(BaseModel):
    result: ReplicationEntry


class ReplicationUpdate(ReplicationCreate, metaclass=ForUpdateMetaclass):
    pass


class ReplicationUpdateArgs(BaseModel):
    id: int
    replication_update: ReplicationUpdate


class ReplicationUpdateResult(BaseModel):
    result: ReplicationEntry


class ReplicationDeleteArgs(BaseModel):
    id: int


class ReplicationDeleteResult(BaseModel):
    result: bool


class ReplicationRunArgs(BaseModel):
    id: int
    really_run: SkipJsonSchema[bool] = True


class ReplicationRunResult(BaseModel):
    result: None


@single_argument_args("replication_run_onetime")
class ReplicationRunOnetimeArgs(ReplicationCreate):
    name: Excluded = excluded_field()
    auto: Excluded = excluded_field()
    schedule: Excluded = excluded_field()
    only_matching_schedule: Excluded = excluded_field()
    enabled: Excluded = excluded_field()
    exclude_mountpoint_property: bool = True
    only_from_scratch: bool = False
    """If `true` then replication will fail if target dataset already exists."""
    mount: bool = True
    """Mount destination file system."""


class ReplicationRunOnetimeResult(BaseModel):
    result: None


class ReplicationListDatasetsArgs(BaseModel):
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    ssh_credentials: int | None = None


class ReplicationListDatasetsResult(BaseModel):
    result: list[str]


class ReplicationCreateDatasetArgs(BaseModel):
    dataset: str
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    ssh_credentials: int | None = None


class ReplicationCreateDatasetResult(BaseModel):
    result: None


class ReplicationListNamingSchemasArgs(BaseModel):
    pass


class ReplicationListNamingSchemasResult(BaseModel):
    result: list[str]


@single_argument_args("count_eligible_manual_snapshots")
class ReplicationCountEligibleManualSnapshotsArgs(BaseModel):
    datasets: list[str] = Field(min_items=1)
    naming_schema: list[SnapshotNameSchema] = []
    name_regex: NonEmptyString | None = None
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    ssh_credentials: int | None = None


@single_argument_result
class ReplicationCountEligibleManualSnapshotsResult(BaseModel):
    total: int
    eligible: int


class ReplicationTargetUnmatchedSnapshotsArgs(BaseModel):
    direction: Literal["PUSH", "PULL"]
    source_datasets: list[str] = Field(min_items=1)
    target_dataset: str
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    ssh_credentials: int | None = None


class ReplicationTargetUnmatchedSnapshotsResult(BaseModel):
    result: dict[str, str] = Field(examples=[
        {
            "backup/work": ["auto-2019-10-15_13-00", "auto-2019-10-15_09-00"],
            "backup/games": ["auto-2019-10-15_13-00"],
        },
    ])
