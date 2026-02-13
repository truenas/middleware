from pydantic import Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'AppRegistryEntry', 'AppRegistryCreateArgs', 'AppRegistryCreateResult', 'AppRegistryUpdateArgs',
    'AppRegistryUpdateResult', 'AppRegistryDeleteArgs', 'AppRegistryDeleteResult',
]


class AppRegistryEntry(BaseModel):
    id: int
    """Unique identifier for the container registry configuration."""
    name: str
    """Human-readable name for the container registry."""
    description: str | None = None
    """Optional description of the container registry or `null`."""
    username: Secret[str]
    """Username for registry authentication (masked for security)."""
    password: Secret[str]
    """Password or access token for registry authentication (masked for security)."""
    uri: str
    """Container registry URI endpoint."""


class AppRegistryCreate(AppRegistryEntry):
    id: Excluded = excluded_field()
    uri: str = 'https://index.docker.io/v1/'
    """Container registry URI endpoint (defaults to Docker Hub)."""


class AppRegistryCreateArgs(BaseModel):
    app_registry_create: AppRegistryCreate
    """Container registry configuration data for the new registry."""


class AppRegistryCreateResult(BaseModel):
    result: AppRegistryEntry
    """The created container registry configuration."""


class AppRegistryUpdate(AppRegistryCreate, metaclass=ForUpdateMetaclass):
    pass


class AppRegistryUpdateArgs(BaseModel):
    id: int
    """ID of the container registry to update."""
    data: AppRegistryUpdate
    """Updated container registry configuration data."""


class AppRegistryUpdateResult(BaseModel):
    result: AppRegistryEntry
    """The updated container registry configuration."""


class AppRegistryDeleteArgs(BaseModel):
    id: int
    """ID of the container registry to delete."""


class AppRegistryDeleteResult(BaseModel):
    result: None
    """Returns `null` when the container registry is successfully deleted."""
