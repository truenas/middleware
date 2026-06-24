from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = [
    "ConfigSaveArgs", "ConfigSaveResult", "ConfigUploadArgs",
    "ConfigUploadResult", "ConfigResetArgs", "ConfigResetResult"
]


class ConfigSave(BaseModel):
    secretseed: bool = Field(
        default=False,
        description="Whether to include the secret seed in the configuration backup.",
    )
    pool_keys: bool = Field(
        default=False,
        description="Whether to include encryption keys for storage pools in the backup. IGNORED and deprecated; "
                    "it does not apply on SCALE systems.",
    )
    root_authorized_keys: bool = Field(
        default=False,
        description="Whether to include root user's SSH authorized keys in the backup.",
    )


class ConfigReset(BaseModel):
    reboot: bool = Field(default=True, description="Whether to reboot the system after resetting configuration.")


class ConfigSaveArgs(BaseModel):
    options: ConfigSave = Field(
        default=ConfigSave(),
        description="Options controlling what data to include in the configuration backup.",
    )


class ConfigSaveResult(BaseModel):
    result: None = Field(description="Returns `null` when the configuration backup is successfully created.")


class ConfigUploadArgs(BaseModel):
    pass


class ConfigUploadResult(BaseModel):
    result: None = Field(description="Returns `null` when the configuration file is successfully uploaded.")


class ConfigResetArgs(BaseModel):
    options: ConfigReset = Field(
        default=ConfigReset(),
        description="Options controlling the configuration reset behavior.",
    )


class ConfigResetResult(BaseModel):
    result: None = Field(description="Returns `null` when the configuration reset is successfully initiated.")
