import middlewared.sqlalchemy as sa


class TwoFactoryUserAuthModel(sa.Model):
    __tablename__ = 'account_twofactor_user_auth'

    id = sa.Column(sa.Integer(), primary_key=True)
    secret = sa.Column(sa.EncryptedText(), nullable=True, default=None)
