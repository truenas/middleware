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
    'AppContainerIdsArgs', 'AppContainerIdsResult', 'AppContainerConsoleChoicesArgs', 'AppContainerConsoleChoicesResult',
    'AppCertificateChoicesArgs', 'AppCertificateChoicesResult', 'AppCertificateAuthorityArgs',
    'AppCertificateAuthorityResult', 'AppUsedPortsArgs', 'AppUsedPortsResult', 'AppIpChoicesArgs', 'AppIpChoicesResult',
    'AppAvailableSpaceArgs', 'AppAvailableSpaceResult', 'AppGpuChoicesArgs', 'AppGpuChoicesResult', 'AppRollbackArgs',
    'AppRollbackResult', 'AppRollbackVersionsArgs', 'AppRollbackVersionsResult', 'AppUpgradeArgs', 'AppUpgradeResult',
    'AppUpgradeSummaryArgs', 'AppUpgradeSummaryResult', 'AppLatestItem',
]


CONTAINER_STATES: TypeAlias = Literal['crashed', 'created', 'exited', 'running', 'starting']


class HostPorts(BaseModel):
    host_port: int
    host_ip: str


class UsedPorts(BaseModel):
    container_port: int
    protocol: str
    host_ports: list[HostPorts]


class AppVolumes(BaseModel):
    source: str
    destination: str
    mode: str
    type_: str = Field(alias='type')


class AppContainerDetails(BaseModel):
    id: str
    service_name: str
    image: str
    port_config: list[UsedPorts]
    state: CONTAINER_STATES
    volume_mounts: list[AppVolumes]


class AppNetworks(BaseModel):
    Name: str
    Id: str
    Labels: dict

    model_config = ConfigDict(extra='allow')


class AppActiveWorkloads(BaseModel):
    containers: int
    used_ports: list[UsedPorts]
    container_details: list[AppContainerDetails]
    volumes: list[AppVolumes]
    images: list[NonEmptyString]
    networks: list[AppNetworks]


class AppEntry(BaseModel):
    name: NonEmptyString
    id: NonEmptyString
    state: Literal['CRASHED', 'DEPLOYING', 'RUNNING', 'STOPPED', 'STOPPING']
    upgrade_available: bool
    latest_version: NonEmptyString | None
    image_updates_available: bool
    custom_app: bool
    migrated: bool
    human_version: NonEmptyString
    version: NonEmptyString
    metadata: dict
    active_workloads: AppActiveWorkloads
    notes: LongString | None
    portals: dict
    version_details: dict | None = None
    config: dict | None = None


@single_argument_args('app_create')
class AppCreateArgs(BaseModel):
    custom_app: bool = False
    values: Secret[dict] = Field(default_factory=dict)
    custom_compose_config: Secret[dict] = Field(default_factory=dict)
    custom_compose_config_string: Secret[LongString] = ''
    catalog_app: str | None = None
    app_name: str = Field(pattern=r'^[a-z]([-a-z0-9]*[a-z0-9])?$', min_length=1, max_length=40)
    '''
    Application name must have the following:
    1) Lowercase alphanumeric characters can be specified
    2) Name must start with an alphabetic character and can end with alphanumeric character
    3) Hyphen '-' is allowed but not as the first or last character
    e.g abc123, abc, abcd-1232
    '''
    train: NonEmptyString = 'stable'
    version: NonEmptyString = 'latest'


class AppCreateResult(BaseModel):
    result: AppEntry


class AppUpdate(BaseModel):
    values: Secret[dict] = Field(default_factory=dict)
    custom_compose_config: Secret[dict] = Field(default_factory=dict)
    custom_compose_config_string: Secret[LongString] = ''


class AppUpdateArgs(BaseModel):
    app_name: NonEmptyString
    update: AppUpdate = AppUpdate()


class AppUpdateResult(BaseModel):
    result: AppEntry


class AppDelete(BaseModel):
    remove_images: bool = True
    remove_ix_volumes: bool = False
    force_remove_ix_volumes: bool = False
    force_remove_custom_app: bool = False


class AppDeleteArgs(BaseModel):
    app_name: NonEmptyString
    options: AppDelete = AppDelete()


class AppDeleteResult(BaseModel):
    result: Literal[True]


class AppConfigArgs(BaseModel):
    app_name: NonEmptyString


class AppConfigResult(BaseModel):
    result: dict


class AppConvertToCustomArgs(BaseModel):
    app_name: NonEmptyString


class AppConvertToCustomResult(BaseModel):
    result: AppEntry


class AppStopArgs(BaseModel):
    app_name: NonEmptyString


class AppStopResult(BaseModel):
    result: None


class AppStartArgs(BaseModel):
    app_name: NonEmptyString


class AppStartResult(BaseModel):
    result: None


class AppRedeployArgs(BaseModel):
    app_name: NonEmptyString


class AppRedeployResult(BaseModel):
    result: AppEntry


class AppOutdatedDockerImagesArgs(BaseModel):
    app_name: NonEmptyString


class AppOutdatedDockerImagesResult(BaseModel):
    result: list[NonEmptyString]


class AppPullImages(BaseModel):
    redeploy: bool = True


class AppPullImagesArgs(BaseModel):
    app_name: NonEmptyString
    options: AppPullImages = AppPullImages()


class AppPullImagesResult(BaseModel):
    result: None


class AppContainerIDOptions(BaseModel):
    alive_only: bool = True


class AppContainerIdsArgs(BaseModel):
    app_name: NonEmptyString
    options: AppContainerIDOptions = AppContainerIDOptions()


class ContainerDetails(BaseModel):
    id: NonEmptyString
    service_name: NonEmptyString
    image: NonEmptyString
    state: CONTAINER_STATES


class AppContainerResponse(RootModel[dict[str, ContainerDetails]]):
    pass


class AppContainerIdsResult(BaseModel):
    result: AppContainerResponse


class AppContainerConsoleChoicesArgs(BaseModel):
    app_name: NonEmptyString


class AppContainerConsoleChoicesResult(BaseModel):
    result: AppContainerResponse


class AppCertificateChoicesArgs(BaseModel):
    pass


class AppCertificate(BaseModel):
    id: int
    name: NonEmptyString


class AppCertificateChoicesResult(BaseModel):
    result: list[AppCertificate]


class AppCertificateAuthorityArgs(BaseModel):
    pass


class AppCertificateAuthorityResult(BaseModel):
    result: list[AppCertificate]


class AppUsedPortsArgs(BaseModel):
    pass


class AppUsedPortsResult(BaseModel):
    result: list[int]


class AppIpChoicesArgs(BaseModel):
    pass


class AppIpChoicesResult(BaseModel):
    result: dict[NonEmptyString, NonEmptyString]


class AppAvailableSpaceArgs(BaseModel):
    pass


class AppAvailableSpaceResult(BaseModel):
    result: int


class AppGpuChoicesArgs(BaseModel):
    pass


class GPU(BaseModel):
    vendor: NonEmptyString | None
    description: LongString | None
    error: NonEmptyString | None
    vendor_specific_config: dict
    gpu_details: dict
    pci_slot: NonEmptyString | None


class AppGPUResponse(RootModel[dict[str, GPU]]):
    pass


class AppGpuChoicesResult(BaseModel):
    result: AppGPUResponse


class AppRollbackOptions(BaseModel):
    app_version: NonEmptyString
    rollback_snapshot: bool = True


class AppRollbackArgs(BaseModel):
    app_name: NonEmptyString
    options: AppRollbackOptions


class AppRollbackResult(BaseModel):
    result: AppEntry


class AppRollbackVersionsArgs(BaseModel):
    app_name: NonEmptyString


class AppRollbackVersionsResult(BaseModel):
    result: list[NonEmptyString]


class UpgradeOptions(BaseModel):
    app_version: NonEmptyString = 'latest'
    values: Secret[dict] = Field(default_factory=dict)
    snapshot_hostpaths: bool = False


class AppUpgradeArgs(BaseModel):
    app_name: NonEmptyString
    options: UpgradeOptions = UpgradeOptions()


class AppUpgradeResult(BaseModel):
    result: AppEntry


class UpgradeSummaryOptions(BaseModel):
    app_version: NonEmptyString = 'latest'


class AppUpgradeSummaryArgs(BaseModel):
    app_name: NonEmptyString
    options: UpgradeSummaryOptions = UpgradeSummaryOptions()


class AppVersionInfo(BaseModel):
    version: str
    '''Version of the app'''
    human_version: str
    '''Human readable version of the app'''


@single_argument_result
class AppUpgradeSummaryResult(BaseModel):
    latest_version: str
    '''Latest version available for the app'''
    latest_human_version: str
    '''Latest human readable version available for the app'''
    upgrade_version: str
    '''Version user has requested to be upgraded at'''
    upgrade_human_version: str
    '''Human readable version user has requested to be upgraded at'''
    available_versions_for_upgrade: list[AppVersionInfo]
    '''List of available versions for upgrade'''
    changelog: LongString | None


class AppAvailableItem(CatalogAppInfo):
    catalog: NonEmptyString
    installed: bool
    train: NonEmptyString


class AppLatestItem(AppAvailableItem):
    pass


class AppCategoriesArgs(BaseModel):
    pass


class AppCategoriesResult(BaseModel):
    result: list[NonEmptyString]


class AppSimilarArgs(BaseModel):
    app_name: NonEmptyString
    train: NonEmptyString


class AppSimilarResult(BaseModel):
    result: list[AppAvailableItem]
