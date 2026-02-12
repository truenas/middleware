from middlewared.api.base import BaseModel

__all__ = [
    "ContainerImageQueryRegistryArgs", "ContainerImageQueryRegistryResult",
]


class ContainerImageQueryRegistryArgs(BaseModel):
    pass


class ContainerImageQueryRegistryResult(BaseModel):
    result: list["ContainerImageQueryRegistryResultImage"]


class ContainerImageQueryRegistryResultImage(BaseModel):
    name: str
    "Image name."
    versions: list["ContainerImageQueryRegistryResultImageVersion"]
    "Available image versions."


class ContainerImageQueryRegistryResultImageVersion(BaseModel):
    version: str
    "Image version name."
