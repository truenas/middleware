from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ["DockerNetworkEntry"]


class DockerNetworkEntry(BaseModel):
    ipam: dict | None = Field(description="IP Address Management configuration for the network or `null`.")
    labels: dict | None = Field(description="Metadata labels attached to the network or `null`.")
    created: NonEmptyString | None = Field(description="Timestamp when the network was created or `null`.")
    driver: NonEmptyString | None = Field(description="Network driver type (bridge, host, overlay, etc.) or `null`.")
    id: NonEmptyString | None = Field(description="Full network identifier or `null`.")
    name: NonEmptyString | None = Field(description="Human-readable name of the network or `null`.")
    scope: NonEmptyString | None = Field(description="Network scope (local, global, swarm) or `null`.")
    short_id: NonEmptyString | None = Field(description="Shortened network identifier or `null`.")
