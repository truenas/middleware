from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString,
                                  single_argument_result)
from .cloud_sync_providers import CloudCredentialProvider

__all__ = ["CredentialsEntry",
           "CredentialsCreateArgs", "CredentialsCreateResult",
           "CredentialsUpdateArgs", "CredentialsUpdateResult",
           "CredentialsDeleteArgs", "CredentialsDeleteResult",
           "CredentialsVerifyArgs", "CredentialsVerifyResult",
           "CredentialsS3ProviderChoicesArgs", "CredentialsS3ProviderChoicesResult"]


class CredentialsEntry(BaseModel):
    id: int
    """Unique identifier for the cloud credential."""
    name: NonEmptyString
    """Human-readable name for the cloud credential."""
    provider: CloudCredentialProvider
    """Cloud provider configuration including type and authentication details."""


class CloudCredentialCreate(CredentialsEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CredentialsCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate
    """Cloud credential configuration data for the new credential."""


class CredentialsCreateResult(BaseModel):
    result: CredentialsEntry
    """The created cloud credential configuration."""


class CredentialsUpdateArgs(BaseModel):
    id: int
    """ID of the cloud credential to update."""
    cloud_sync_credentials_update: CloudCredentialUpdate
    """Updated cloud credential configuration data."""


class CredentialsUpdateResult(BaseModel):
    result: CredentialsEntry
    """The updated cloud credential configuration."""


class CredentialsDeleteArgs(BaseModel):
    id: int
    """ID of the cloud credential to delete."""


class CredentialsDeleteResult(BaseModel):
    result: bool
    """Returns `true` when the cloud credential is successfully deleted."""


class CredentialsVerifyArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialProvider
    """Cloud provider configuration to verify connectivity and authentication."""


@single_argument_result
class CredentialsVerifyResult(BaseModel):
    valid: bool
    """Whether the cloud credentials are valid and functional."""
    error: LongString | None = None
    """Error message if credential verification failed or `null` on success."""
    excerpt: LongString | None = None
    """Logs excerpt (or `null` if no error occurred)."""


class CredentialsS3ProviderChoicesArgs(BaseModel):
    pass


class CredentialsS3ProviderChoicesResult(BaseModel):
    result: dict[str, str]
