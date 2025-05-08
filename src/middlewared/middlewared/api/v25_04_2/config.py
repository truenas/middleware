from middlewared.api.base import BaseModel


__all__ = [
    "ConfigSaveArgs", "ConfigSaveResult", "ConfigUploadArgs",
    "ConfigUploadResult", "ConfigResetArgs", "ConfigResetResult"
]


class ConfigSave(BaseModel):
    secretseed: bool = False
    pool_keys: bool = False
    root_authorized_keys: bool = False


class ConfigReset(BaseModel):
    reboot: bool = True


class ConfigSaveArgs(BaseModel):
    options: ConfigSave = ConfigSave()


class ConfigSaveResult(BaseModel):
    result: None


class ConfigUploadArgs(BaseModel):
    pass


class ConfigUploadResult(BaseModel):
    result: None


class ConfigResetArgs(BaseModel):
    options: ConfigReset = ConfigReset()


class ConfigResetResult(BaseModel):
    result: None
