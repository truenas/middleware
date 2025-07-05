from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args,
)


__all__ = [
    'ContainerConfigEntry',
    'ContainerConfigUpdateArgs', 'ContainerConfigUpdateResult',
]


class ContainerConfigEntry(BaseModel):
    id: int
    image_dataset: str | None = None


@single_argument_args('container_config_update')
class ContainerConfigUpdateArgs(ContainerConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ContainerConfigUpdateResult(BaseModel):
    result: ContainerConfigEntry
