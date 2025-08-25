from middlewared.api.base import BaseModel

__all__ = [
    "ContainerImagePullArgs", "ContainerImagePullResult",
]


class ContainerImagePullArgs(BaseModel):
    url: str
    """Image URL."""
    name: str
    """Local name for the image."""


class ContainerImagePullResult(BaseModel):
    result: None
