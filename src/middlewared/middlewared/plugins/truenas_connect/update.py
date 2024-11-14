import middlewared.sqlalchemy as sa
from middlewared.service import ConfigService


class TrueCommandModel(sa.Model):
    __tablename__ = 'truenas_connect'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False, nullable=False)
    claim_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    jwt_token = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    system_id = sa.Column(sa.String(255), default=None, nullable=True)
    acme_key = sa.Column(sa.EncryptedText(), default=None, nullable=True)
    acme_account_uri = sa.Column(sa.String(255), default=None, nullable=True)
    acme_directory_uri = sa.Column(sa.String(255), default=None, nullable=True)


class TrueNASConnectService(ConfigService):

    # TODO: Add roles
    class Config:
        datastore = 'truenas_connect'
        cli_private = True
        namespace = 'tn_connect'
