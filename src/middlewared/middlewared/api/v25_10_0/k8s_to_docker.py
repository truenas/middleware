from pydantic import Field, RootModel

from middlewared.api.base import BaseModel, single_argument_result


__all__ = [
    'K8sToDockerListBackupsArgs', 'K8sToDockerListBackupsResult', 'K8sToDockerMigrateArgs', 'K8sToDockerMigrateResult',
]


class K8sToDockerListBackupsArgs(BaseModel):
    kubernetes_pool: str


class ReleaseDetails(BaseModel):
    error: str | None = None
    helm_secret: dict = Field(default_factory=dict)
    release_secrets: dict = Field(default_factory=dict)
    train: str | None = None
    app_name: str | None = None
    app_version: str | None = None
    release_name: str
    migrate_file_path: str | None = None


class BackupDetails(BaseModel):
    name: str
    releases: list[ReleaseDetails]
    skipped_releases: list[ReleaseDetails]
    snapshot_name: str
    created_on: str
    backup_path: str


class Backups(RootModel[dict[str, BackupDetails]]):
    pass


@single_argument_result
class K8sToDockerListBackupsResult(BaseModel):
    error: str | None
    backups: Backups


class MigrateOptions(BaseModel):
    backup_name: str | None = None


class K8sToDockerMigrateArgs(BaseModel):
    kubernetes_pool: str
    options: MigrateOptions = MigrateOptions()


class AppMigrationDetails(BaseModel):
    name: str
    successfully_migrated: bool
    error: str | None


class K8sToDockerMigrateResult(BaseModel):
    result: list[AppMigrationDetails]
