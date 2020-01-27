"""Simplify and clean up idmap backends

Revision ID: f6a18dec20fa
Revises: bc290fddc888
Create Date: 2020-01-24 13:34:04.998905+00:00

"""
from alembic import op
import sqlalchemy as sa
import json


# revision identifiers, used by Alembic.
revision = 'f6a18dec20fa'
down_revision = 'bc290fddc888'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    conn = op.get_bind()
    m = {}
    highest_seen = 0
    configured_domains = [dict(row) for row in conn.execute("SELECT * FROM directoryservice_idmap_domaintobackend").fetchall()]
    for domain in configured_domains:
        m[domain['idmap_dtb_domain_id']] = {}
        backend = domain['idmap_dtb_idmap_backend']
        dom = domain['idmap_dtb_domain_id']

        idmap_table = f"directoryservice_idmap_{backend}"

        backend_data = [dict(row) for row in conn.execute(f"SELECT * FROM {idmap_table} WHERE "
                                                          f"idmap_{backend}_domain_id = ?", dom).fetchall()]

        m[dom]['backend'] = backend
        if not backend_data:
            m[dom].update({
                'range_low': None,
                'range_high': None,
            })
            continue

        prefix_len = len(f"idmap_{backend}_")
        for k, v in backend_data[0].items():
            if k == 'id' or k[prefix_len:] == 'domain_id':
                continue

            m[dom].update({k[prefix_len:]: v})

        if m[dom]['range_high'] > highest_seen:
            highest_seen = m[dom]['range_high']

    op.drop_table('directoryservice_idmap_script')
    op.drop_table('directoryservice_idmap_tdb')
    op.drop_table('directoryservice_idmap_rid')
    op.drop_table('directoryservice_idmap_ad')
    with op.batch_alter_table('directoryservice_idmap_rfc2307', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_idmap_rfc2307_idmap_rfc2307_certificate_id')

    op.drop_table('directoryservice_idmap_rfc2307')
    with op.batch_alter_table('directoryservice_idmap_ldap', schema=None) as batch_op:
        batch_op.drop_index('ix_directoryservice_idmap_ldap_idmap_ldap_certificate_id')

    op.drop_table('directoryservice_idmap_ldap')
    op.drop_table('directoryservice_idmap_domaintobackend')

    op.drop_table('directoryservice_idmap_nss')
    op.drop_table('directoryservice_idmap_autorid')
    with op.batch_alter_table('directoryservice_activedirectory', schema=None) as batch_op:
        batch_op.drop_column('idmap_backend')

    with op.batch_alter_table('directoryservice_ldap', schema=None) as batch_op:
        batch_op.drop_column('idmap_backend')

    with op.batch_alter_table('directoryservice_idmap_domain', schema=None) as batch_op:
        batch_op.add_column(sa.Column('idmap_domain_certificate_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('idmap_domain_idmap_backend', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('idmap_domain_options', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('idmap_domain_range_high', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('idmap_domain_range_low', sa.Integer(), nullable=True))

    for domain, params in m.items():
        range_low = params.pop('range_low')
        range_high = params.pop('range_high')
        certificate_id = params.pop('certificate_id', '')
        if range_low is None:
            range_low = highest_seen + 1
            range_high = highest_seen + 100000000

        backend = params.pop('backend')
        conn.execute("UPDATE directoryservice_idmap_domain SET idmap_domain_idmap_backend = :backend, "
                     "idmap_domain_range_low = :low, idmap_domain_range_high = :high, "
                     "idmap_domain_certificate_id = :cert, idmap_domain_options = :opts "
                     "WHERE idmap_domain_name= :dom",
                     low=range_low, high=range_high, backend=backend, cert=certificate_id,
                     opts=json.dumps(params) if params else '', dom=domain)

    with op.batch_alter_table('directoryservice_idmap_domain', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_directoryservice_idmap_domain_idmap_domain_certificate_id'), ['idmap_domain_certificate_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_directoryservice_idmap_domain_idmap_domain_certificate_id_system_certificate'), 'system_certificate', ['idmap_domain_certificate_id'], ['id'])
        batch_op.alter_column('idmap_domain_idmap_backend', nullable=False)
        batch_op.alter_column('idmap_domain_options', nullable=False)
        batch_op.alter_column('idmap_domain_range_low', nullable=False)
        batch_op.alter_column('idmap_domain_range_high', nullable=False)

    # ### end Alembic commands ###
