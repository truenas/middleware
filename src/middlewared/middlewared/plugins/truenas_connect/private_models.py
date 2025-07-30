from middlewared.api.base import BaseModel, ForUpdateMetaclass, HttpsOnlyURL, single_argument_args


@single_argument_args('tn_connect_update_environment')
class TrueNASConnectUpdateEnvironmentArgs(BaseModel, metaclass=ForUpdateMetaclass):
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL
