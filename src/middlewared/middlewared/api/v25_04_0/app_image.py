from typing import Literal

from middlewared.api.base import BaseModel, LongString, NonEmptyString, single_argument_args, single_argument_result

__all__ = [
    'AppImageEntry', 'ContainerImagesDockerhubRateLimitArgs', 'ContainerImagesDockerhubRateLimitResult',
    'AppImagePullArgs', 'AppImagePullResult', 'AppImageDeleteArgs', 'AppImageDeleteResult',
]


class AppImageParsedRepoTags(BaseModel):
    reference: str
    image: str
    tag: str
    registry: str
    complete_tag: str
    reference_is_digest: bool


class AppImageEntry(BaseModel):
    id: NonEmptyString
    repo_tags: list[str]
    repo_digests: list[str]
    size: int
    dangling: bool
    update_available: bool
    created: str
    author: str
    comment: LongString
    parsed_repo_tags: list[AppImageParsedRepoTags] | None = None


class ContainerImagesDockerhubRateLimitArgs(BaseModel):
    pass


@single_argument_result
class ContainerImagesDockerhubRateLimitResult(BaseModel):
    total_pull_limit: int | None = None
    '''Total pull limit for Docker Hub registry'''
    total_time_limit_in_secs: int | None = None
    '''Total time limit in seconds for Docker Hub registry before the limit renews'''
    remaining_pull_limit: int | None = None
    '''Remaining pull limit for Docker Hub registry'''
    remaining_time_limit_in_secs: int | None = None
    '''Remaining time limit in seconds for Docker Hub registry for the current pull limit to be renewed'''
    error: str | None = None


class AppImageAuthConfig(BaseModel):
    username: str
    password: str
    registry_uri: str | None = None


@single_argument_args('image_pull')
class AppImagePullArgs(BaseModel):
    auth_config: AppImageAuthConfig | None = None
    image: NonEmptyString


class AppImagePullResult(BaseModel):
    result: None


class AppImageDeleteOptions(BaseModel):
    force: bool = False


class AppImageDeleteArgs(BaseModel):
    image_id: str
    options: AppImageDeleteOptions = AppImageDeleteOptions()


class AppImageDeleteResult(BaseModel):
    result: Literal[True]
