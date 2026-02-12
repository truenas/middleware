from middlewared.api.base import BaseModel


__all__ = [
    "ConfigSaveArgs", "ConfigSaveResult", "ConfigUploadArgs",
    "ConfigUploadResult", "ConfigResetArgs", "ConfigResetResult"
]


class ConfigSave(BaseModel):
    secretseed: bool = False
    """Whether to include the secret seed in the configuration backup."""
    pool_keys: bool = False
    """Whether to include encryption keys for storage pools in the backup."""
    root_authorized_keys: bool = False
    """Whether to include root user's SSH authorized keys in the backup."""


class ConfigReset(BaseModel):
    reboot: bool = True
    """Whether to reboot the system after resetting configuration."""


class ConfigSaveArgs(BaseModel):
    options: ConfigSave = ConfigSave()
    """Options controlling what data to include in the configuration backup."""


class ConfigSaveResult(BaseModel):
    result: None
    """Returns `null` when the configuration backup is successfully created."""


class ConfigUploadArgs(BaseModel):
    pass


class ConfigUploadResult(BaseModel):
    result: None
    """Returns `null` when the configuration file is successfully uploaded."""


class ConfigResetArgs(BaseModel):
    options: ConfigReset = ConfigReset()
    """Options controlling the configuration reset behavior."""


class ConfigResetResult(BaseModel):
    result: None
    """Returns `null` when the configuration reset is successfully initiated."""
