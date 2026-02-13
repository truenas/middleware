from typing import Literal

from middlewared.api.base import BaseModel, LongString, NonEmptyString, single_argument_args, single_argument_result

__all__ = [
    'AppImageEntry', 'ContainerImagesDockerhubRateLimitArgs', 'ContainerImagesDockerhubRateLimitResult',
    'AppImagePullArgs', 'AppImagePullResult', 'AppImageDeleteArgs', 'AppImageDeleteResult',
]


class AppImageParsedRepoTags(BaseModel):
    reference: str
    """Full reference to the container image (registry/repository:tag)."""
    image: str
    """Container image name without registry or tag."""
    tag: str
    """Image tag (version) or digest identifier."""
    registry: str
    """Container registry hostname (e.g., docker.io, quay.io)."""
    complete_tag: str
    """Complete image reference including registry, image name, and tag."""
    reference_is_digest: bool
    """Whether the reference uses a digest hash instead of a tag name."""


class AppImageEntry(BaseModel):
    id: NonEmptyString
    """Unique identifier for the container image (usually SHA256 hash)."""
    repo_tags: list[str]
    """Array of repository tags associated with this image."""
    repo_digests: list[str]
    """Array of repository digests (content-addressable identifiers) for this image."""
    size: int
    """Size of the container image in bytes."""
    dangling: bool
    """Whether this is a dangling image (no tags or references)."""
    update_available: bool
    """Whether a newer version of this image is available for download."""
    created: str | None
    """Timestamp when the container image was created (ISO format) or `null` if not available."""
    author: str | None
    """Author or maintainer of the container image or `null` if not specified."""
    comment: LongString | None
    """Comment or description provided by the image author or `null` if not provided."""
    parsed_repo_tags: list[AppImageParsedRepoTags] | None = None
    """Parsed repository tag information or `null` if not available."""


class ContainerImagesDockerhubRateLimitArgs(BaseModel):
    pass


@single_argument_result
class ContainerImagesDockerhubRateLimitResult(BaseModel):
    total_pull_limit: int | None = None
    """Total pull limit for Docker Hub registry."""
    total_time_limit_in_secs: int | None = None
    """Total time limit in seconds for Docker Hub registry before the limit renews."""
    remaining_pull_limit: int | None = None
    """Remaining pull limit for Docker Hub registry."""
    remaining_time_limit_in_secs: int | None = None
    """Remaining time limit in seconds for Docker Hub registry for the current pull limit to be renewed."""
    error: str | None = None
    """Error message if rate limit information could not be retrieved or `null` on success."""


class AppImageAuthConfig(BaseModel):
    username: str
    """Username for container registry authentication."""
    password: str
    """Password or access token for container registry authentication."""
    registry_uri: str | None = None
    """Container registry URI or `null` to use default registry."""


@single_argument_args('image_pull')
class AppImagePullArgs(BaseModel):
    auth_config: AppImageAuthConfig | None = None
    """Authentication configuration for private registries or `null` for public images."""
    image: NonEmptyString
    """Container image reference to pull (registry/repository:tag)."""


class AppImagePullResult(BaseModel):
    result: None
    """Returns `null` when the image is successfully pulled."""


class AppImageDeleteOptions(BaseModel):
    force: bool = False
    """Whether to force deletion even if the image is in use by containers."""


class AppImageDeleteArgs(BaseModel):
    image_id: str
    """Container image ID or reference to delete."""
    options: AppImageDeleteOptions = AppImageDeleteOptions()
    """Deletion options controlling force removal behavior."""


class AppImageDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the container image is successfully deleted."""
