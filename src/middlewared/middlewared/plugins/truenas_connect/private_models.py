from middlewared.api.base import BaseModel, ForUpdateMetaclass, HttpsOnlyURL
from middlewared.api.current import TrueNASConnectEntry


class TrueNASConnectUpdateEnvironment(BaseModel, metaclass=ForUpdateMetaclass):
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL


class TrueNASConnectUpdateEnvironmentArgs(BaseModel):
    tn_connect_update_environment: TrueNASConnectUpdateEnvironment


class TrueNASConnectUpdateEnvironmentResult(BaseModel):
    result: TrueNASConnectEntry
