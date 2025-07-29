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
    """"00" - "59\""""


class ReplicationLifetimeModel(BaseModel):
    schedule: CronModel
    """Cron schedule for when snapshot retention policies are applied."""
    lifetime_value: int = Field(ge=1)
    """Number of time units to retain snapshots."""
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"]
    """Time unit for snapshot retention."""


class ReplicationEntry(BaseModel):
    id: int
    """Unique identifier for this replication task."""
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
    """Which side actively establishes the netcat connection for `SSH+NETCAT` transport.

    * `LOCAL`: Local system initiates the connection
    * `REMOTE`: Remote system initiates the connection
    * `null`: Not applicable for other transport types
    """
    netcat_active_side_listen_address: str | None = None
    """IP address for the active side to listen on for `SSH+NETCAT` transport. `null` if not applicable."""
    netcat_active_side_port_min: TcpPort | None = None
    """Minimum port number in the range for netcat connections. `null` if not applicable."""
    netcat_active_side_port_max: TcpPort | None = None
    """Maximum port number in the range for netcat connections. `null` if not applicable."""
    netcat_passive_side_connect_address: str | None = None
    """IP address for the passive side to connect to for `SSH+NETCAT` transport. `null` if not applicable."""
    sudo: bool = False
    """`SSH` and `SSH+NETCAT` transports should use sudo (which is expected to be passwordless) to run `zfs` \
    command on the remote machine."""
    source_datasets: list[str] = Field(min_length=1)
    """List of datasets to replicate snapshots from."""
    target_dataset: str
    """Dataset to put snapshots into."""
    recursive: bool
    """Whether to recursively replicate child datasets."""
    exclude: list[str] = []
    """Array of dataset patterns to exclude from replication."""
    properties: bool = True
    """Send dataset properties along with snapshots."""
    properties_exclude: list[NonEmptyString] = []
    """Array of dataset property names to exclude from replication."""
    properties_override: dict[str, str] = {}
    """Object mapping dataset property names to override values during replication."""
    replicate: bool = False
    """Whether to use ZFS replication streams for more efficient transfer."""
    encryption: bool = False
    """Whether to enable encryption for the replicated datasets."""
    encryption_inherit: bool | None = None
    """Whether replicated datasets should inherit encryption from parent. `null` if encryption is disabled."""
    encryption_key: str | None = None
    """Encryption key for replicated datasets. `null` if not specified."""
    encryption_key_format: Literal["HEX", "PASSPHRASE"] | None = None
    """Format of the encryption key.

    * `HEX`: Hexadecimal-encoded key
    * `PASSPHRASE`: Text passphrase
    * `null`: Not applicable when encryption is disabled
    """
    encryption_key_location: str | None = None
    """Filesystem path where encryption key is stored. `null` if not using key file."""
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
    """Number of time units to retain snapshots for custom retention policy. Only applies when `retention_policy` is \
    CUSTOM."""
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"] | None = None
    """Time unit for snapshot retention for custom retention policy. Only applies when `retention_policy` is CUSTOM."""
    lifetimes: list[ReplicationLifetimeModel] = []
    """Array of different retention schedules with their own cron schedules and lifetime settings."""
    compression: Literal["LZ4", "PIGZ", "PLZIP"] | None = None
    """Compresses SSH stream. Available only for SSH transport."""
    speed_limit: int | None = Field(default=None, ge=1)
    """Limits speed of SSH stream. Available only for SSH transport."""
    large_block: bool = True
    """Enable large block support for ZFS send streams."""
    embed: bool = False
    """Enable embedded block support for ZFS send streams."""
    compressed: bool = True
    """Enable compressed ZFS send streams."""
    retries: int = Field(default=5, ge=1)
    """Number of retries before considering replication failed."""
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] | None = None
    """Log level for replication task execution. Controls verbosity of replication logs."""
    enabled: bool = True
    """Whether this replication task is enabled."""
    state: dict
    """Current state information for the replication task."""
    job: dict | None
    """Information about the currently running job. `null` if no job is running."""
    has_encrypted_dataset_keys: bool
    """Whether this replication task has encrypted dataset keys available."""


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
    """Configuration for creating a new replication task."""


class ReplicationCreateResult(BaseModel):
    result: ReplicationEntry
    """The newly created replication task configuration."""


class ReplicationUpdate(ReplicationCreate, metaclass=ForUpdateMetaclass):
    pass


class ReplicationUpdateArgs(BaseModel):
    id: int
    """ID of the replication task to update."""
    replication_update: ReplicationUpdate
    """Updated configuration for the replication task."""


class ReplicationUpdateResult(BaseModel):
    result: ReplicationEntry
    """The updated replication task configuration."""


class ReplicationDeleteArgs(BaseModel):
    id: int
    """ID of the replication task to delete."""


class ReplicationDeleteResult(BaseModel):
    result: bool
    """Whether the replication task was successfully deleted."""


class ReplicationRunArgs(BaseModel):
    id: int
    """ID of the replication task to run."""
    really_run: SkipJsonSchema[bool] = True
    """Internal flag to confirm the operation should proceed."""


class ReplicationRunResult(BaseModel):
    result: None
    """Returns `null` on successful replication task execution."""


@single_argument_args("replication_run_onetime")
class ReplicationRunOnetimeArgs(ReplicationCreate):
    name: Excluded = excluded_field()
    auto: Excluded = excluded_field()
    schedule: Excluded = excluded_field()
    only_matching_schedule: Excluded = excluded_field()
    enabled: Excluded = excluded_field()
    exclude_mountpoint_property: bool = True
    """Whether to exclude the mountpoint property from replication."""
    only_from_scratch: bool = False
    """If `true` then replication will fail if target dataset already exists."""
    mount: bool = True
    """Mount destination file system."""


class ReplicationRunOnetimeResult(BaseModel):
    result: None
    """Returns `null` on successful one-time replication execution."""


class ReplicationListDatasetsArgs(BaseModel):
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    """Transport method to use for listing datasets."""
    ssh_credentials: int | None = None
    """Keychain credential ID for SSH access. `null` for local transport."""


class ReplicationListDatasetsResult(BaseModel):
    result: list[str]
    """Array of dataset names available for replication."""


class ReplicationCreateDatasetArgs(BaseModel):
    dataset: str
    """Name of the dataset to create."""
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    """Transport method to use for dataset creation."""
    ssh_credentials: int | None = None
    """Keychain credential ID for SSH access. `null` for local transport."""


class ReplicationCreateDatasetResult(BaseModel):
    result: None
    """Returns `null` on successful dataset creation."""


class ReplicationListNamingSchemasArgs(BaseModel):
    pass


class ReplicationListNamingSchemasResult(BaseModel):
    result: list[str]
    """Array of available snapshot naming schema patterns."""


@single_argument_args("count_eligible_manual_snapshots")
class ReplicationCountEligibleManualSnapshotsArgs(BaseModel):
    datasets: list[str] = Field(min_length=1)
    """Array of dataset names to count snapshots for."""
    naming_schema: list[SnapshotNameSchema] = []
    """Array of naming schema patterns to match against."""
    name_regex: NonEmptyString | None = None
    """Regular expression to match snapshot names. `null` to match all names."""
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    """Transport method to use for accessing snapshots."""
    ssh_credentials: int | None = None
    """Keychain credential ID for SSH access. `null` for local transport."""


@single_argument_result
class ReplicationCountEligibleManualSnapshotsResult(BaseModel):
    total: int
    """Total number of snapshots found."""
    eligible: int
    """Number of snapshots eligible for replication."""


class ReplicationTargetUnmatchedSnapshotsArgs(BaseModel):
    direction: Literal["PUSH", "PULL"]
    """Direction of replication to check for unmatched snapshots."""
    source_datasets: list[str] = Field(min_length=1)
    """Array of source dataset names."""
    target_dataset: str
    """Target dataset name to check for unmatched snapshots."""
    transport: Literal["SSH", "SSH+NETCAT", "LOCAL"]
    """Transport method to use for accessing snapshots."""
    ssh_credentials: int | None = None
    """Keychain credential ID for SSH access. `null` for local transport."""


class ReplicationTargetUnmatchedSnapshotsResult(BaseModel):
    result: dict[str, str] = Field(examples=[
        {
            "backup/work": ["auto-2019-10-15_13-00", "auto-2019-10-15_09-00"],
            "backup/games": ["auto-2019-10-15_13-00"],
        },
    ])
    """Object mapping dataset names to arrays of unmatched snapshot names on the target side."""
