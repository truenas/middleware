"""Convert API keys to SCRAM auth

Revision ID: 055cfee51499
Revises: 9202ee4732cf
Create Date: 2026-02-06 18:18:37.674898+00:00

"""
from alembic import op
import sqlalchemy as sa
import truenas_pyscram
from base64 import b64encode, b64decode
from middlewared.utils.pwenc import encrypt


# revision identifiers, used by Alembic.
revision = '055cfee51499'
down_revision = '9202ee4732cf'
branch_labels = None
depends_on = None


DEFAULT_ITERS = 500000


def revoke_api_key(api_key, reason):
    api_key['iterations'] = 0
    api_key['expiry'] = -1
    api_key['revoked_reason'] = reason
    api_key['stored_key'] = encrypt('')
    api_key['server_key'] = encrypt('')
    api_key['salt'] = encrypt('')


def add_scram_data(api_key, iter, saltb64, hashb64):
    key_hash = truenas_pyscram.CryptoDatum(b64decode(hashb64))
    salt = truenas_pyscram.CryptoDatum(b64decode(saltb64))
    auth_data = truenas_pyscram.generate_scram_auth_data(iterations=iter, salt=salt, salted_password=key_hash)
    api_key['stored_key'] = encrypt(b64encode(bytes(auth_data.stored_key)).decode())
    api_key['server_key'] = encrypt(b64encode(bytes(auth_data.server_key)).decode())
    api_key['salt'] = encrypt(b64encode(bytes(salt)).decode())
    api_key['iterations'] = iter


def convert_api_keys():
    conn = op.get_bind()
    api_keys = conn.execute(sa.text('SELECT * FROM account_api_key')).fetchall()

    for key in api_keys:
        api_key = {
            'id': key.id,
            'expiry': key.expiry,
            'revoked_reason': key.revoked_reason,
            'key': key.key,
            'iterations': key.iterations,
            'salt': key.salt,
            'server_key': key.server_key,
            'stored_key': key.stored_key,
        }
        try:
            algo, iters, saltb64, hashb64 = api_key['key'].rsplit('$', 3)
            iters = int(iters)
        except Exception:
            # We really don't want to break here. We'll just revoke key if it's invalid.
            revoke_api_key(api_key, 'Invalid API key')
        else:
            if algo != '$pbkdf2-sha512':
                # NOTE: in versions of TrueNAS prior to 25.04 API keys were generated
                # using pbkdf2-sha256 with a small number of iterations. During the
                # release cycles for 25.04 and 25.10 we upgraded these API keys on
                # the fly from pbkdf2-sha256 to pbkdf2-sha512. As a consequence the
                # number of users with the older-style keys in active use will be
                # very limited.
                #
                # This means there is a practical impact to the change that people
                # who skip those versions and go straight to 26 or later will have
                # to generate new API keys. This would have to be a runtime migration
                # that we don't want to continue to support forever.
                revoke_api_key(api_key, f'{algo}: unsupported cryptographic algorithm')
            elif iters != DEFAULT_ITERS:
                revoke_api_key(api_key, f'{iters}: unexpected iteration count')
            else:
                add_scram_data(api_key, iters, saltb64, hashb64)

        stmt = (
            'UPDATE account_api_key SET '
            'iterations = :iters, '
            'server_key = :server_key, '
            'stored_key = :stored_key, '
            'salt = :salt, '
            'expiry = :expiry, '
            'revoked_reason = :reason '
            'WHERE id = :apikeyid'
        )

        conn.execute(sa.text(stmt), {
            'iters': api_key['iterations'],
            'server_key': api_key['server_key'],
            'stored_key': api_key['stored_key'],
            'salt': api_key['salt'],
            'expiry': api_key['expiry'],
            'reason': api_key['revoked_reason'],
            'apikeyid': api_key['id'],
        })


def upgrade():
    with op.batch_alter_table('account_api_key', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iterations', sa.Integer(), server_default=str(DEFAULT_ITERS), nullable=False))
        batch_op.add_column(sa.Column('salt', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('server_key', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('stored_key', sa.Text(), nullable=True))

    convert_api_keys()

    with op.batch_alter_table('account_api_key', schema=None) as batch_op:
        batch_op.alter_column('salt', nullable=False)
        batch_op.alter_column('server_key', nullable=False)
        batch_op.alter_column('stored_key', nullable=False)

    # Now that we've transformed the initial key into the new auth-data we can drop the column
    with op.batch_alter_table('account_api_key', schema=None) as batch_op:
        batch_op.drop_column('key')

    # ### end Alembic commands ###
