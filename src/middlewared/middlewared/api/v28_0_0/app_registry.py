from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    'AppRegistryEntry', 'AppRegistryCreate', 'AppRegistryUpdate',
    'AppRegistryCreateArgs', 'AppRegistryCreateResult',
    'AppRegistryUpdateArgs', 'AppRegistryUpdateResult',
    'AppRegistryDeleteArgs', 'AppRegistryDeleteResult',
]


class AppRegistryEntry(BaseModel):
    id: int = Field(description="Unique identifier for the container registry configuration.")
    name: str = Field(description="Human-readable name for the container registry.")
    description: str | None = Field(
        default=None,
        description="Optional description of the container registry or `null`.",
    )
    username: Secret[str] = Field(description="Username for registry authentication (masked for security).")
    password: Secret[str] = Field(
        description="Password or access token for registry authentication (masked for security).",
    )
    uri: str = Field(description="Container registry URI endpoint.")


class AppRegistryCreate(AppRegistryEntry):
    id: Excluded = excluded_field()
    uri: str = Field(
        default='https://index.docker.io/v1/',
        description="Container registry URI endpoint (defaults to Docker Hub).",
    )


class AppRegistryCreateArgs(BaseModel):
    app_registry_create: AppRegistryCreate = Field(
        description="Container registry configuration data for the new registry.",
    )


class AppRegistryCreateResult(BaseModel):
    result: AppRegistryEntry = Field(description="The created container registry configuration.")


class AppRegistryUpdate(AppRegistryCreate, metaclass=ForUpdateMetaclass):
    pass


class AppRegistryUpdateArgs(BaseModel):
    id: int = Field(description="ID of the container registry to update.")
    data: AppRegistryUpdate = Field(description="Updated container registry configuration data.")


class AppRegistryUpdateResult(BaseModel):
    result: AppRegistryEntry = Field(description="The updated container registry configuration.")


class AppRegistryDeleteArgs(BaseModel):
    id: int = Field(description="ID of the container registry to delete.")


class AppRegistryDeleteResult(BaseModel):
    result: None = Field(description="Returns `null` when the container registry is successfully deleted.")
