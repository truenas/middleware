from pydantic import Field, RootModel

from middlewared.api.base import BaseModel, single_argument_result


__all__ = [
    'K8stoDockerMigrationListBackupsArgs', 'K8stoDockerMigrationListBackupsResult', 'K8stoDockerMigrationMigrateArgs', 'K8stoDockerMigrationMigrateResult',
]


class K8stoDockerMigrationListBackupsArgs(BaseModel):
    kubernetes_pool: str
    """Name of the ZFS pool where Kubernetes data is stored."""


class ReleaseDetails(BaseModel):
    error: str | None = None
    """Error message if the release has migration issues or `null` if no errors."""
    helm_secret: dict = Field(default_factory=dict)
    """Helm secret data for the release."""
    release_secrets: dict = Field(default_factory=dict)
    """Application-specific secret data for the release."""
    train: str | None = None
    """Application catalog train name or `null` if not available."""
    app_name: str | None = None
    """Name of the application or `null` if not available."""
    app_version: str | None = None
    """Version of the application or `null` if not available."""
    release_name: str
    """Name of the Helm release."""
    migrate_file_path: str | None = None
    """Path to the migration configuration file or `null` if not available."""


class BackupDetails(BaseModel):
    name: str
    """Name of the backup."""
    releases: list[ReleaseDetails]
    """Array of releases included in this backup."""
    skipped_releases: list[ReleaseDetails]
    """Array of releases that were skipped during backup creation."""
    snapshot_name: str
    """Name of the ZFS snapshot for this backup."""
    created_on: str
    """Timestamp when the backup was created."""
    backup_path: str
    """File system path where the backup data is stored."""


class Backups(RootModel[dict[str, BackupDetails]]):
    pass


@single_argument_result
class K8stoDockerMigrationListBackupsResult(BaseModel):
    error: str | None
    """Error message if backup listing failed or `null` if successful."""
    backups: Backups
    """Object containing available Kubernetes-to-Docker migration backups."""


class MigrateOptions(BaseModel):
    backup_name: str | None = None
    """Name of the specific backup to migrate or `null` to migrate the latest."""


class K8stoDockerMigrationMigrateArgs(BaseModel):
    kubernetes_pool: str
    """Name of the ZFS pool where Kubernetes data is stored."""
    options: MigrateOptions = MigrateOptions()
    """Migration options controlling the migration process."""


class AppMigrationDetails(BaseModel):
    name: str
    """Name of the application that was migrated."""
    successfully_migrated: bool
    """Whether the application was successfully migrated to Docker."""
    error: str | None
    """Error message if migration failed or `null` if successful."""


class K8stoDockerMigrationMigrateResult(BaseModel):
    result: list[AppMigrationDetails]
    """Array of migration results for each application."""
