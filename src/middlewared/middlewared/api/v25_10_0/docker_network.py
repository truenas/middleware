from pydantic import ConfigDict

from middlewared.api.base import BaseModel, NonEmptyString


class DockerNetworkEntry(BaseModel):
    ipam: dict | None
    labels: dict | None
    created: NonEmptyString | None
    driver: NonEmptyString | None
    id: NonEmptyString | None
    name: NonEmptyString | None
    scope: NonEmptyString | None
    short_id: NonEmptyString | None
