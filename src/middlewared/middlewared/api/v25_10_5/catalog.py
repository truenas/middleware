from datetime import datetime

from pydantic import ConfigDict, Field, RootModel

from middlewared.api.base import BaseModel, ForUpdateMetaclass, LongString, NonEmptyString, single_argument_args

__all__ = [
    'CatalogEntry', 'CatalogUpdateArgs', 'CatalogUpdateResult', 'CatalogTrainsArgs', 'CatalogTrainsResult',
    'CatalogSyncArgs', 'CatalogSyncResult', 'CatalogAppInfo', 'CatalogAppsArgs', 'CatalogAppsResult',
    'CatalogGetAppDetailsArgs', 'CatalogGetAppDetailsResult',
]


class CatalogEntry(BaseModel):
    id: NonEmptyString = Field(description="Unique identifier for the catalog.")
    label: NonEmptyString = Field(
        pattern=r'^\w+[\w.-]*$',
        description="Catalog identifier. Must start with alphanumeric, then allow alphanumeric, periods, and hyphens.",
    )
    preferred_trains: list[NonEmptyString] = Field(description="Array of preferred train names for this catalog.")
    location: NonEmptyString = Field(description="Git repository URL or local path to the catalog.")


@single_argument_args('catalog_update')
class CatalogUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    preferred_trains: list[NonEmptyString] = Field(
        description="Updated array of preferred train names for the catalog.",
    )


class CatalogUpdateResult(BaseModel):
    result: CatalogEntry = Field(description="The updated catalog configuration.")


class CatalogTrainsArgs(BaseModel):
    pass


class CatalogTrainsResult(BaseModel):
    result: list[NonEmptyString] = Field(description="Array of available train names in the catalog.")


class CatalogSyncArgs(BaseModel):
    pass


class CatalogSyncResult(BaseModel):
    result: None = Field(description="Returns `null` when the catalog sync is successfully completed.")


class Maintainer(BaseModel):
    name: str = Field(description="Name of the app maintainer.")
    email: str = Field(description="Email address of the app maintainer.")
    url: str | None = Field(description="Website URL of the app maintainer or `null`.")


class CatalogAppInfo(BaseModel):
    app_readme: LongString | None = Field(description="HTML content of the app README.")
    categories: list[str] = Field(description="List of categories for the app.")
    description: str = Field(description="Short description of the app.")
    healthy: bool = Field(description="Health status of the app.")
    healthy_error: str | None = Field(default=None, description="Error if app is not healthy.")
    home: str = Field(description="Homepage URL of the app.")
    location: str = Field(description="Local path to the app's location.")
    latest_version: str | None = Field(description="Latest available app version.")
    latest_app_version: str | None = Field(description="Latest available app version in repository.")
    latest_human_version: str | None = Field(description="Human-readable version of the app.")
    last_update: datetime | None = Field(description="Timestamp of the last update in ISO format.")
    name: str = Field(description="Name of the app.")
    recommended: bool = Field(description="Indicates if the app is recommended.")
    title: str = Field(description="Title of the app.")
    maintainers: list[Maintainer] = Field(description="List of app maintainers.")
    tags: list[str] = Field(description="Tags associated with the app.")
    screenshots: list[str] = Field(description="List of screenshot URLs.")
    sources: list[str] = Field(description="List of source URLs.")
    icon_url: str | None = Field(default=None, description="URL of the app icon.")

    # We do this because if we change anything in catalog.json, even older releases will
    # get this new field and different roles will start breaking due to this
    model_config = ConfigDict(extra='allow')


@single_argument_args('catalog_apps_options')
class CatalogAppsArgs(BaseModel):
    cache: bool = Field(default=True, description="Whether to use cached catalog data if available.")
    cache_only: bool = Field(default=False, description="Whether to only return cached data without fetching updates.")
    retrieve_all_trains: bool = Field(default=True, description="Whether to retrieve apps from all available trains.")
    trains: list[NonEmptyString] = Field(
        default_factory=list,
        description="Specific train names to retrieve apps from (empty array means all trains).",
    )


class CatalogTrainInfo(RootModel[dict[str, CatalogAppInfo]]):
    pass


class CatalogAppsResult(BaseModel):
    result: dict[str, CatalogTrainInfo] = Field(description="Object mapping train names to their app information.")


class CatalogAppVersionDetails(BaseModel):
    train: NonEmptyString = Field(description="Train name where the app version is located.")


class CatalogGetAppDetailsArgs(BaseModel):
    app_name: NonEmptyString = Field(description="Name of the app to get details for.")
    app_version_details: CatalogAppVersionDetails = Field(
        description="Version and train information for the specific app.",
    )


class CatalogGetAppDetailsResult(BaseModel):
    result: CatalogAppInfo = Field(description="Detailed information about the requested app.")
