from datetime import datetime

from pydantic import ConfigDict, Field, RootModel

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args, LongString


__all__ = [
    'CatalogEntry', 'CatalogUpdateArgs', 'CatalogUpdateResult', 'CatalogTrainsArgs', 'CatalogTrainsResult',
    'CatalogSyncArgs', 'CatalogSyncResult', 'CatalogAppInfo', 'CatalogAppsArgs', 'CatalogAppsResult',
    'CatalogGetAppDetailsArgs', 'CatalogGetAppDetailsResult',
]


class CatalogEntry(BaseModel):
    id: NonEmptyString
    """Unique identifier for the catalog."""
    label: NonEmptyString = Field(pattern=r'^\w+[\w.-]*$')
    """Human-readable label for the catalog."""
    preferred_trains: list[NonEmptyString]
    """Array of preferred train names for this catalog."""
    location: NonEmptyString
    """Git repository URL or local path to the catalog."""


@single_argument_args('catalog_update')
class CatalogUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    preferred_trains: list[NonEmptyString]
    """Updated array of preferred train names for the catalog."""


class CatalogUpdateResult(BaseModel):
    result: CatalogEntry
    """The updated catalog configuration."""


class CatalogTrainsArgs(BaseModel):
    pass


class CatalogTrainsResult(BaseModel):
    result: list[NonEmptyString]
    """Array of available train names in the catalog."""


class CatalogSyncArgs(BaseModel):
    pass


class CatalogSyncResult(BaseModel):
    result: None
    """Returns `null` when the catalog sync is successfully completed."""


class Maintainer(BaseModel):
    name: str
    """Name of the app maintainer."""
    email: str
    """Email address of the app maintainer."""
    url: str | None
    """Website URL of the app maintainer or `null`."""


class CatalogAppInfo(BaseModel):
    app_readme: LongString | None
    """HTML content of the app README."""
    categories: list[str]
    """List of categories for the app."""
    description: str
    """Short description of the app."""
    healthy: bool
    """Health status of the app."""
    healthy_error: str | None = None
    """Error if app is not healthy."""
    home: str
    """Homepage URL of the app."""
    location: str
    """Local path to the app's location."""
    latest_version: str | None
    """Latest available app version."""
    latest_app_version: str | None
    """Latest available app version in repository."""
    latest_human_version: str | None
    """Human-readable version of the app."""
    last_update: datetime | None
    """Timestamp of the last update in ISO format."""
    name: str
    """Name of the app."""
    recommended: bool
    """Indicates if the app is recommended."""
    title: str
    """Title of the app."""
    maintainers: list[Maintainer]
    """List of app maintainers."""
    tags: list[str]
    """Tags associated with the app."""
    screenshots: list[str]
    """List of screenshot URLs."""
    sources: list[str]
    """List of source URLs."""
    icon_url: str | None = None
    """URL of the app icon."""

    # We do this because if we change anything in catalog.json, even older releases will
    # get this new field and different roles will start breaking due to this
    model_config = ConfigDict(extra='allow')


@single_argument_args('catalog_apps_options')
class CatalogAppsArgs(BaseModel):
    cache: bool = True
    """Whether to use cached catalog data if available."""
    cache_only: bool = False
    """Whether to only return cached data without fetching updates."""
    retrieve_all_trains: bool = True
    """Whether to retrieve apps from all available trains."""
    trains: list[NonEmptyString] = Field(default_factory=list)
    """Specific train names to retrieve apps from (empty array means all trains)."""


class CatalogTrainInfo(RootModel[dict[str, CatalogAppInfo]]):
    pass


class CatalogAppsResult(BaseModel):
    result: dict[str, CatalogTrainInfo]
    """Object mapping train names to their app information."""


class CatalogAppVersionDetails(BaseModel):
    train: NonEmptyString
    """Train name where the app version is located."""


class CatalogGetAppDetailsArgs(BaseModel):
    app_name: NonEmptyString
    """Name of the app to get details for."""
    app_version_details: CatalogAppVersionDetails
    """Version and train information for the specific app."""


class CatalogGetAppDetailsResult(BaseModel):
    result: CatalogAppInfo
    """Detailed information about the requested app."""
