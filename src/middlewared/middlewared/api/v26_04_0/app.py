from typing import Literal, TypeAlias

from pydantic import ConfigDict, Field, RootModel, Secret

from middlewared.api.base import BaseModel, LongString, NonEmptyString, single_argument_args, single_argument_result

from .catalog import CatalogAppInfo


__all__ = [
    'AppCategoriesArgs', 'AppCategoriesResult', 'AppSimilarArgs', 'AppSimilarResult', 'AppAvailableItem',
    'AppEntry', 'AppCreateArgs', 'AppCreateResult', 'AppUpdateArgs', 'AppUpdateResult', 'AppDeleteArgs',
    'AppDeleteResult', 'AppConfigArgs', 'AppConfigResult', 'AppConvertToCustomArgs', 'AppConvertToCustomResult',
    'AppStopArgs', 'AppStopResult', 'AppStartArgs', 'AppStartResult', 'AppRedeployArgs', 'AppRedeployResult',
    'AppOutdatedDockerImagesArgs', 'AppOutdatedDockerImagesResult', 'AppPullImagesArgs', 'AppPullImagesResult',
    'AppContainerIdsArgs', 'AppContainerIdsResult', 'AppContainerConsoleChoicesArgs',
    'AppContainerConsoleChoicesResult', 'AppCertificateChoicesArgs', 'AppCertificateChoicesResult',
    'AppUsedPortsArgs', 'AppUsedPortsResult', 'AppUsedHostIpsArgs', 'AppUsedHostIpsResult',
    'AppIpChoicesArgs', 'AppIpChoicesResult', 'AppAvailableSpaceArgs', 'AppAvailableSpaceResult',
    'AppGpuChoicesArgs', 'AppGpuChoicesResult', 'AppRollbackArgs',
    'AppRollbackResult', 'AppRollbackVersionsArgs', 'AppRollbackVersionsResult', 'AppUpgradeArgs', 'AppUpgradeResult',
    'AppUpgradeSummaryArgs', 'AppUpgradeSummaryResult', 'AppContainerLogsFollowTailEventSourceArgs',
    'AppContainerLogsFollowTailEventSourceEvent', 'AppStatsEventSourceArgs', 'AppStatsEventSourceEvent',
    'AppLatestItem',
]


CONTAINER_STATES: TypeAlias = Literal['crashed', 'created', 'exited', 'running', 'starting']


class HostPorts(BaseModel):
    host_port: int
    """The port number on the host system."""
    host_ip: str
    """The IP address on the host system that the port is bound to."""


class UsedPorts(BaseModel):
    container_port: int
    """The port number inside the container."""
    protocol: str = Field(examples=['tcp', 'udp'])
    """The network protocol used."""
    host_ports: list[HostPorts]
    """Array of host port mappings for this container port."""


class AppVolumes(BaseModel):
    source: str
    """The source path or volume name on the host system."""
    destination: str
    """The mount path inside the container."""
    mode: str
    """The mount mode (e.g., 'rw' for read-write, 'ro' for read-only)."""
    type_: str = Field(alias='type', examples=['bind', 'volume'])
    """The volume type."""


class AppContainerDetails(BaseModel):
    id: str
    """Unique identifier for the container."""
    service_name: str
    """Name of the service this container provides."""
    image: str
    """Docker image name and tag used by this container."""
    port_config: list[UsedPorts]
    """Array of port mappings for this container."""
    state: CONTAINER_STATES
    """Current state of the container."""
    volume_mounts: list[AppVolumes]
    """Array of volume mounts configured for this container."""


class AppNetworks(BaseModel):
    Name: str
    """The name of the Docker network."""
    Id: str
    """Unique identifier for the Docker network."""
    Labels: dict
    """Key-value pairs of labels associated with the network."""

    model_config = ConfigDict(extra='allow')


class AppActiveWorkloads(BaseModel):
    containers: int
    """Total number of containers currently running for this application."""
    used_ports: list[UsedPorts]
    """Array of all port mappings used by the application."""
    used_host_ips: list[str]
    """Array of host IP addresses in use by the application."""
    container_details: list[AppContainerDetails]
    """Detailed information about each container in the application."""
    volumes: list[AppVolumes]
    """Array of all volume mounts used by the application."""
    images: list[NonEmptyString]
    """Array of Docker image names used by the application."""
    networks: list[AppNetworks]
    """Array of Docker networks associated with the application."""


class AppEntry(BaseModel):
    name: NonEmptyString
    """The display name of the application."""
    id: NonEmptyString
    """Unique identifier for the application instance."""
    state: Literal['CRASHED', 'DEPLOYING', 'RUNNING', 'STOPPED', 'STOPPING']
    """Current operational state of the application."""
    upgrade_available: bool
    """Whether a newer version of the application is available for upgrade."""
    latest_version: NonEmptyString | None
    """The latest available version string, or `null` if no updates are available."""
    image_updates_available: bool
    """Whether newer Docker images are available for the containers in this application."""
    custom_app: bool
    """Whether this is a custom application (`true`) or from a catalog (`false`)."""
    migrated: bool
    """Whether this application has been migrated from kubernetes."""
    source: Literal['TRUENAS', 'EXTERNAL'] = 'TRUENAS'
    """Source of the application: 'TRUENAS' for managed apps, 'EXTERNAL' for unmanaged containers."""
    human_version: NonEmptyString
    """Human-readable version string for display purposes."""
    version: NonEmptyString
    """Technical version identifier of the currently installed application."""
    metadata: dict
    """Application metadata including description, category, and other catalog information."""
    active_workloads: AppActiveWorkloads
    """Information about the running containers, ports, and resources used by this application."""
    notes: LongString | None
    """User-provided notes or comments about this application instance."""
    portals: dict
    """Web portals and access points provided by the application (URLs, ports, etc.)."""
    version_details: dict | None = None
    """Detailed version information including changelog and upgrade notes. `null` if not available."""
    config: dict | None = None
    """Current configuration values for the application. `null` if configuration is not requested."""


@single_argument_args('app_create')
class AppCreateArgs(BaseModel):
    custom_app: bool = False
    """Whether to create a custom application (`true`) or install from catalog (`false`)."""
    values: Secret[dict] = Field(default_factory=dict)
    """Configuration values for the application installation."""
    custom_compose_config: Secret[dict] = Field(default_factory=dict)
    """Docker Compose configuration as a structured object for custom applications."""
    custom_compose_config_string: Secret[LongString] = ''
    """Docker Compose configuration as a YAML string for custom applications."""
    catalog_app: str | None = None
    """Name of the catalog application to install. Required when `custom_app` is `false`."""
    app_name: str = Field(
        examples=['abc123', 'abc', 'abcd-1232'], pattern='^[a-z]([-a-z0-9]*[a-z0-9])?$', min_length=1, max_length=40
    )
    """
    Application name must have the following:

    * Lowercase alphanumeric characters can be specified.
    * Name must start with an alphabetic character and can end with alphanumeric character.
    * Hyphen '-' is allowed but not as the first or last character.
    """
    train: NonEmptyString = Field(default='stable', examples=['stable', 'enterprise'])
    """The catalog train to install from."""
    version: NonEmptyString = Field(default='latest', examples=['latest', '1.2.3'])
    """The version of the application to install."""


class AppCreateResult(BaseModel):
    result: AppEntry
    """The newly created application entry with all configuration details."""


class AppUpdate(BaseModel):
    values: Secret[dict] = Field(default_factory=dict)
    """Updated configuration values for the application."""
    custom_compose_config: Secret[dict] = Field(default_factory=dict)
    """Updated Docker Compose configuration as a structured object."""
    custom_compose_config_string: Secret[LongString] = ''
    """Updated Docker Compose configuration as a YAML string."""


class AppUpdateArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to update."""
    update: AppUpdate = AppUpdate()
    """Updated configuration and settings for the application."""


class AppUpdateResult(BaseModel):
    result: AppEntry
    """The updated application entry with new configuration details."""


class AppDelete(BaseModel):
    remove_images: bool = True
    """Whether to remove Docker images associated with the application."""
    remove_ix_volumes: bool = False
    """Whether to remove TrueNAS-managed storage volumes."""
    force_remove_ix_volumes: bool = False
    """Force removal of TrueNAS-managed volumes even if they contain data."""
    force_remove_custom_app: bool = False
    """Force removal of custom applications that might have important data or configurations."""


class AppDeleteArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to delete."""
    options: AppDelete = AppDelete()
    """Options controlling what gets removed along with the application."""


class AppDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the application is successfully deleted."""


class AppConfigArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to retrieve configuration for."""


class AppConfigResult(BaseModel):
    result: dict
    """The current configuration object for the application."""


class AppConvertToCustomArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the catalog application to convert to a custom application."""


class AppConvertToCustomResult(BaseModel):
    result: AppEntry
    """The application entry after conversion to a custom application."""


class AppStopArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to stop."""


class AppStopResult(BaseModel):
    result: None
    """Returns `null` when the application is successfully stopped."""


class AppStartArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to start."""


class AppStartResult(BaseModel):
    result: None
    """Returns `null` when the application is successfully started."""


class AppRedeployArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to redeploy (stop, pull latest images, and restart)."""


class AppRedeployResult(BaseModel):
    result: AppEntry
    """The application entry after successful redeployment."""


class AppOutdatedDockerImagesArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to check for outdated Docker images."""


class AppOutdatedDockerImagesResult(BaseModel):
    result: list[NonEmptyString]
    """Array of Docker image names that have updates available."""


class AppPullImages(BaseModel):
    redeploy: bool = True
    """Whether to redeploy the application after pulling new images."""


class AppPullImagesArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to pull images for."""
    options: AppPullImages = AppPullImages()
    """Options for pulling images including whether to redeploy."""


class AppPullImagesResult(BaseModel):
    result: None
    """Returns `null` when the application images are successfully pulled."""


class AppContainerIDOptions(BaseModel):
    alive_only: bool = True
    """Whether to return only running/active containers (`true`) or include all containers (`false`)."""


class AppContainerIdsArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to get container IDs for."""
    options: AppContainerIDOptions = AppContainerIDOptions()
    """Options for filtering the returned container list."""


class ContainerDetails(BaseModel):
    id: NonEmptyString
    """Unique identifier for the container."""
    service_name: NonEmptyString
    """Name of the service this container provides."""
    image: NonEmptyString
    """Docker image name and tag used by this container."""
    state: CONTAINER_STATES
    """Current state of the container."""


class AppContainerResponse(RootModel[dict[str, ContainerDetails]]):
    """Object mapping container IDs to their detailed information."""
    pass


class AppContainerIdsResult(BaseModel):
    result: AppContainerResponse
    """Object containing container ID to details mappings."""


class AppContainerConsoleChoicesArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to get console choices for."""


class AppContainerConsoleChoicesResult(BaseModel):
    result: AppContainerResponse
    """Object containing container choices available for console access."""


class AppCertificateChoicesArgs(BaseModel):
    pass


class AppCertificate(BaseModel):
    id: int
    """Unique identifier for the certificate."""
    name: NonEmptyString
    """Display name of the certificate."""


class AppCertificateChoicesResult(BaseModel):
    result: list[AppCertificate]
    """Array of available certificates that can be used by applications."""


class AppUsedPortsArgs(BaseModel):
    pass


class AppUsedPortsResult(BaseModel):
    result: list[int]
    """Array of port numbers currently in use by any application."""


class AppUsedHostIpsArgs(BaseModel):
    pass


class AppUsedHostIpsResult(BaseModel):
    result: dict[str, list[str]]
    """Object mapping application names to arrays of host IP addresses they use."""


class AppIpChoicesArgs(BaseModel):
    pass


class AppIpChoicesResult(BaseModel):
    result: dict[NonEmptyString, NonEmptyString]
    """Object mapping IP addresses to their descriptive names."""


class AppAvailableSpaceArgs(BaseModel):
    pass


class AppAvailableSpaceResult(BaseModel):
    result: int
    """Available disk space in bytes for application storage."""


class AppGpuChoicesArgs(BaseModel):
    pass


class GPU(BaseModel):
    vendor: NonEmptyString | None = Field(examples=["NVIDIA", "AMD", "Intel"])
    """GPU vendor name. `null` if not detected."""
    description: LongString | None
    """Human-readable description of the GPU device. `null` if not available."""
    error: NonEmptyString | None
    """Error message if the GPU cannot be accessed or configured. `null` if no errors."""
    vendor_specific_config: dict
    """Configuration options specific to the GPU vendor."""
    gpu_details: dict
    """Detailed information about the GPU hardware and capabilities."""
    pci_slot: NonEmptyString | None
    """PCI slot identifier where the GPU is installed. `null` if not available."""


class AppGPUResponse(RootModel[dict[str, GPU]]):
    pass


class AppGpuChoicesResult(BaseModel):
    result: AppGPUResponse
    """Object mapping GPU identifiers to their detailed information."""


class AppRollbackOptions(BaseModel):
    app_version: NonEmptyString
    """Target version to rollback to."""
    rollback_snapshot: bool = True
    """Whether to create a snapshot before performing the rollback."""


class AppRollbackArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to rollback."""
    options: AppRollbackOptions
    """Rollback options."""


class AppRollbackResult(BaseModel):
    result: AppEntry
    """The application entry after successful rollback."""


class AppRollbackVersionsArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to get rollback versions for."""


class AppRollbackVersionsResult(BaseModel):
    result: list[NonEmptyString]
    """Array of version strings available for rollback."""


class UpgradeOptions(BaseModel):
    app_version: NonEmptyString = 'latest'
    """Target version to upgrade to. Use 'latest' for the newest available version."""
    values: Secret[dict] = Field(default_factory=dict)
    """Configuration values to apply during the upgrade."""
    snapshot_hostpaths: bool = False
    """Whether to create snapshots of host path volumes before upgrade."""


class AppUpgradeArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to upgrade."""
    options: UpgradeOptions = UpgradeOptions()
    """Options controlling the upgrade process including target version and snapshot behavior."""


class AppUpgradeResult(BaseModel):
    result: AppEntry
    """The application entry after successful upgrade."""


class UpgradeSummaryOptions(BaseModel):
    app_version: NonEmptyString = 'latest'
    """Target version to generate upgrade summary for. Use 'latest' for the newest available version."""


class AppUpgradeSummaryArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to get upgrade summary for."""
    options: UpgradeSummaryOptions = UpgradeSummaryOptions()
    """Options specifying the target version for the summary."""


class AppVersionInfo(BaseModel):
    version: str
    """Version of the app."""
    human_version: str
    """Human-readable version of the app."""


@single_argument_result
class AppUpgradeSummaryResult(BaseModel):
    latest_version: str
    """Latest version available for the app."""
    latest_human_version: str
    """Latest human readable version available for the app."""
    upgrade_version: str
    """Version user has requested to be upgraded at."""
    upgrade_human_version: str
    """Human-readable version user has requested to be upgraded at."""
    available_versions_for_upgrade: list[AppVersionInfo]
    """List of available versions for upgrade."""
    changelog: LongString | None
    """Changelog or release notes for the upgrade version. `null` if not available."""


class AppAvailableItem(CatalogAppInfo):
    catalog: NonEmptyString
    """Name of the catalog this application comes from."""
    installed: bool
    """Whether this application is currently installed on the system."""
    train: NonEmptyString = Field(examples=['stable', 'enterprise'])
    """The catalog train this application version belongs to."""
    popularity_rank: int | None
    """Popularity ranking of this application. Lower numbers indicate higher popularity. `null` if not ranked."""


class AppLatestItem(AppAvailableItem):
    """Represents the latest version of an available application."""
    pass


class AppCategoriesArgs(BaseModel):
    pass


class AppCategoriesResult(BaseModel):
    result: list[NonEmptyString]
    """Array of available application category names."""


class AppSimilarArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the application to find similar apps for."""
    train: NonEmptyString = Field(examples=['stable', 'enterprise'])
    """The catalog train to search within."""


class AppSimilarResult(BaseModel):
    result: list[AppAvailableItem]
    """Array of applications similar to the requested one."""


class AppContainerLogsFollowTailEventSourceArgs(BaseModel):
    tail_lines: int | None = Field(default=500, ge=1)
    """Number of log lines to tail from the end of the log. If `null`, retrieve complete logs of the container."""
    app_name: str
    """Name of the application whose container logs to follow."""
    container_id: str
    """Unique identifier of the specific container to get logs from."""


@single_argument_result
class AppContainerLogsFollowTailEventSourceEvent(BaseModel):
    data: str
    """The log line content."""
    timestamp: str | None
    """Timestamp of the log entry. `null` if not available."""


class AppStatsEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2)
    """Interval in seconds between statistics updates."""


class AppStatsEventSourceEvent(BaseModel):
    result: list["AppStatsEventSourceEventItem"]
    """Array of statistics for each running application."""


class AppStatsEventSourceEventItem(BaseModel):
    app_name: str
    """Name of the application these statistics are for."""
    cpu_usage: int
    """Percentage of cpu used by an app."""
    memory: int
    """Current memory (in bytes) used by an app."""
    networks: list["AppStatsEventSourceEventItemNetwork"]
    """Array of network interface statistics for the application."""
    blkio: "AppStatsEventSourceEventItemBlkio"
    """Block I/O statistics for the application."""


class AppStatsEventSourceEventItemNetwork(BaseModel):
    interface_name: str
    """Name of the interface used by the app."""
    rx_bytes: int
    """Received bytes/s by an interface."""
    tx_bytes: int
    """Transmitted bytes/s by an interface."""


class AppStatsEventSourceEventItemBlkio(BaseModel):
    read: int
    """Blkio read bytes."""
    write: int
    """Blkio write bytes."""


AppStatsEventSourceEvent.model_rebuild()
