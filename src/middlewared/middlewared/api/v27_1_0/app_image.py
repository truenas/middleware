from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, LongString, NonEmptyString, single_argument_args, single_argument_result

__all__ = [
    'AppImageEntry', 'ContainerImagesDockerhubRateLimitArgs', 'ContainerImagesDockerhubRateLimitResult',
    'AppImagePullArgs', 'AppImagePullResult', 'AppImageDeleteArgs', 'AppImageDeleteResult',
]


class AppImageParsedRepoTags(BaseModel):
    reference: str = Field(description="Full reference to the container image (registry/repository:tag).")
    image: str = Field(description="Container image name without registry or tag.")
    tag: str = Field(description="Image tag (version) or digest identifier.")
    registry: str = Field(description="Container registry hostname (e.g., docker.io, quay.io).")
    complete_tag: str = Field(description="Complete image reference including registry, image name, and tag.")
    reference_is_digest: bool = Field(description="Whether the reference uses a digest hash instead of a tag name.")


class AppImageEntry(BaseModel):
    id: NonEmptyString = Field(description="Unique identifier for the container image (usually SHA256 hash).")
    repo_tags: list[str] = Field(description="Array of repository tags associated with this image.")
    repo_digests: list[str] = Field(
        description="Array of repository digests (content-addressable identifiers) for this image.",
    )
    size: int = Field(description="Size of the container image in bytes.")
    dangling: bool = Field(description="Whether this is a dangling image (no tags or references).")
    update_available: bool = Field(description="Whether a newer version of this image is available for download.")
    created: str | None = Field(
        description="Timestamp when the container image was created (ISO format) or `null` if not available.",
    )
    author: str | None = Field(description="Author or maintainer of the container image or `null` if not specified.")
    comment: LongString | None = Field(
        description="Comment or description provided by the image author or `null` if not provided.",
    )
    parsed_repo_tags: list[AppImageParsedRepoTags] | None = Field(
        default=None,
        description="Parsed repository tag information or `null` if not available.",
    )


class ContainerImagesDockerhubRateLimitArgs(BaseModel):
    pass


@single_argument_result
class ContainerImagesDockerhubRateLimitResult(BaseModel):
    total_pull_limit: int | None = Field(default=None, description="Total pull limit for Docker Hub registry.")
    total_time_limit_in_secs: int | None = Field(
        default=None,
        description="Total time limit in seconds for Docker Hub registry before the limit renews.",
    )
    remaining_pull_limit: int | None = Field(default=None, description="Remaining pull limit for Docker Hub registry.")
    remaining_time_limit_in_secs: int | None = Field(
        default=None,
        description="Remaining time limit in seconds for Docker Hub registry for the current pull limit to be renewed.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if rate limit information could not be retrieved or `null` on success.",
    )


class AppImageAuthConfig(BaseModel):
    username: Secret[str] = Field(description="Username for container registry authentication.")
    password: Secret[str] = Field(description="Password or access token for container registry authentication.")
    registry_uri: str | None = Field(
        default=None,
        description="Container registry URI or `null` to use default registry.",
    )


@single_argument_args('image_pull')
class AppImagePullArgs(BaseModel):
    auth_config: AppImageAuthConfig | None = Field(
        default=None,
        description="Authentication configuration for private registries or `null` for public images.",
    )
    image: NonEmptyString = Field(description="Container image reference to pull (registry/repository:tag).")


class AppImagePullResult(BaseModel):
    result: None = Field(description="Returns `null` when the image is successfully pulled.")


class AppImageDeleteOptions(BaseModel):
    force: bool = Field(
        default=False,
        description="Whether to force deletion even if the image is in use by containers.",
    )


class AppImageDeleteArgs(BaseModel):
    image_id: str = Field(description="Container image ID or reference to delete.")
    options: AppImageDeleteOptions = Field(
        default=AppImageDeleteOptions(),
        description="Deletion options controlling force removal behavior.",
    )


class AppImageDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the container image is successfully deleted.")
