from pydantic import Field

from middlewared.api.base import BaseModel, Multiline, NonEmptyString

__all__ = [
    "FilesystemCompatibilityPathConsumer",
    "FilesystemCompatibilityCompatibilityWarningsArgs",
    "FilesystemCompatibilityCompatibilityWarningsResult",
]


class FilesystemCompatibilityPathConsumer(BaseModel):
    service: NonEmptyString = Field(description="Namespace of the service the consumer belongs to.")
    id: int | str = Field(description="Identifier of the consumer: the share, task or container id, or the app name.")
    name: Multiline[NonEmptyString] = Field(description="Human-readable name of the consumer.")
    path: NonEmptyString = Field(description="The host path the consumer uses.")


class FilesystemCompatibilityCompatibilityWarningsArgs(BaseModel):
    path: NonEmptyString = Field(description="The host path a consumer wants to use.")
    service: NonEmptyString = Field(description="Namespace of the service the consumer belongs to.")


class FilesystemCompatibilityCompatibilityWarningsResult(BaseModel):
    result: list[FilesystemCompatibilityPathConsumer] = Field(
        description="The consumers that conflict with the caller on `path`.",
    )
