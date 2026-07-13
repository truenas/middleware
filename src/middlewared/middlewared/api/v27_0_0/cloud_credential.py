from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    LongString,
    NonEmptyString,
    excluded_field,
)

from .cloud_sync_providers import CloudCredentialProvider

__all__ = ["CloudCredentialProvider",
           "CloudCredentialCreate", "CloudCredentialUpdate",
           "CredentialsEntry",
           "CredentialsCreateArgs", "CredentialsCreateResult",
           "CredentialsUpdateArgs", "CredentialsUpdateResult",
           "CredentialsDeleteArgs", "CredentialsDeleteResult",
           "CredentialsVerifyArgs", "CredentialsVerifyData", "CredentialsVerifyResult",
           "CredentialsS3ProviderChoicesArgs", "CredentialsS3ProviderChoicesResult"]


class CredentialsEntry(BaseModel):
    id: int = Field(description="Unique identifier for the cloud credential.")
    name: NonEmptyString = Field(description="Human-readable name for the cloud credential.")
    provider: CloudCredentialProvider = Field(
        description="Cloud provider configuration including type and authentication details.",
    )


class CloudCredentialCreate(CredentialsEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CredentialsCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate = Field(
        description="Cloud credential configuration data for the new credential.",
    )


class CredentialsCreateResult(BaseModel):
    result: CredentialsEntry = Field(description="The created cloud credential configuration.")


class CredentialsUpdateArgs(BaseModel):
    id: int = Field(description="ID of the cloud credential to update.")
    cloud_sync_credentials_update: CloudCredentialUpdate = Field(
        description="Updated cloud credential configuration data.",
    )


class CredentialsUpdateResult(BaseModel):
    result: CredentialsEntry = Field(description="The updated cloud credential configuration.")


class CredentialsDeleteArgs(BaseModel):
    id: int = Field(description="ID of the cloud credential to delete.")


class CredentialsDeleteResult(BaseModel):
    result: bool = Field(description="Returns `true` when the cloud credential is successfully deleted.")


class CredentialsVerifyArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialProvider = Field(
        description="Cloud provider configuration to verify connectivity and authentication.",
    )


class CredentialsVerifyData(BaseModel):
    valid: bool = Field(description="Whether the cloud credentials are valid and functional.")
    error: LongString | None = Field(
        default=None,
        description="Error message if credential verification failed or `null` on success.",
    )
    excerpt: LongString | None = Field(default=None, description="Logs excerpt (or `null` if no error occurred).")


class CredentialsVerifyResult(BaseModel):
    result: CredentialsVerifyData = Field(description="Outcome of the cloud credential verification.")


class CredentialsS3ProviderChoicesArgs(BaseModel):
    pass


class CredentialsS3ProviderChoicesResult(BaseModel):
    result: dict[str, str]
