from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ["DockerNetworkEntry"]


class DockerNetworkEntry(BaseModel):
    ipam: dict | None
    """IP Address Management configuration for the network or `null`."""
    labels: dict | None
    """Metadata labels attached to the network or `null`."""
    created: NonEmptyString | None
    """Timestamp when the network was created or `null`."""
    driver: NonEmptyString | None
    """Network driver type (bridge, host, overlay, etc.) or `null`."""
    id: NonEmptyString | None
    """Full network identifier or `null`."""
    name: NonEmptyString | None
    """Human-readable name of the network or `null`."""
    scope: NonEmptyString | None
    """Network scope (local, global, swarm) or `null`."""
    short_id: NonEmptyString | None
    """Shortened network identifier or `null`."""
