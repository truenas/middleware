from middlewared.api.base import BaseModel, HttpUrl, NonEmptyString

__all__ = [
    "ContainerImagePullArgs", "ContainerImagePullResult",
]


class ContainerImagePullArgs(BaseModel):
    url: HttpUrl
    """Image URL."""
    name: NonEmptyString
    """Local name for the image."""


class ContainerImagePullResult(BaseModel):
    result: None
