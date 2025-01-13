from pydantic import Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'AppRegistryEntry', 'AppRegistryCreateArgs', 'AppRegistryCreateResult', 'AppRegistryUpdateArgs',
    'AppRegistryUpdateResult', 'AppRegistryDeleteArgs', 'AppRegistryDeleteResult',
]


class AppRegistryEntry(BaseModel):
    id: int
    name: str
    description: str | None = None
    username: Secret[str]
    password: Secret[str]
    uri: str


class AppRegistryCreate(AppRegistryEntry):
    id: Excluded = excluded_field()
    uri: str = 'https://registry-1.docker.io/'


class AppRegistryCreateArgs(BaseModel):
    app_registry_create: AppRegistryCreate


class AppRegistryCreateResult(BaseModel):
    result: AppRegistryEntry


class AppRegistryUpdate(AppRegistryCreate, metaclass=ForUpdateMetaclass):
    pass


class AppRegistryUpdateArgs(BaseModel):
    id: int
    data: AppRegistryUpdate


class AppRegistryUpdateResult(BaseModel):
    result: AppRegistryEntry


class AppRegistryDeleteArgs(BaseModel):
    id: int


class AppRegistryDeleteResult(BaseModel):
    result: None
