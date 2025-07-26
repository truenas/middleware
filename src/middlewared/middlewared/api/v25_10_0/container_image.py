from middlewared.api.base import BaseModel

__all__ = [
    'ContainerImagePullArgs', 'ContainerImagePullResult',
]


class ContainerImagePullArgs(BaseModel):
    url: str
    name: str


class ContainerImagePullResult(BaseModel):
    result: None
