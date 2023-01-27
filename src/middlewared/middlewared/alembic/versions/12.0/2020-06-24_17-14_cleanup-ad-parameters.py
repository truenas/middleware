"""cleanup AD parameters

Revision ID: 25962b409a1e
Revises: 71a8d1e504a7
Create Date: 2020-06-24 17:14:26.706480+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25962b409a1e'
down_revision = '71a8d1e504a7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('directoryservice_activedirectory', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_activedirectory_ad_certificate_id')
        batch_op.drop_column('ad_ldap_sasl_wrapping')
        batch_op.drop_column('ad_certificate_id')
        batch_op.drop_column('ad_ssl')
        batch_op.drop_column('ad_validate_certificates')

    # ### end Alembic commands ###
