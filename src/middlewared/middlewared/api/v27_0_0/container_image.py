from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = [
    "ContainerImageQueryRegistryArgs", "ContainerImageQueryRegistryResult",
    "ContainerImageQueryRegistryResultImage", "ContainerImageQueryRegistryResultImageVersion",
]


class ContainerImageQueryRegistryArgs(BaseModel):
    pass


class ContainerImageQueryRegistryResult(BaseModel):
    result: list["ContainerImageQueryRegistryResultImage"]


class ContainerImageQueryRegistryResultImage(BaseModel):
    name: str = Field(description="Image name.")
    versions: list["ContainerImageQueryRegistryResultImageVersion"] = Field(description="Available image versions.")


class ContainerImageQueryRegistryResultImageVersion(BaseModel):
    version: str = Field(description="Image version name.")
