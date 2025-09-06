"""fix network_alias table

Revision ID: 6e41203881b2
Revises: a3f3b07bb1aa
Create Date: 2021-12-20 20:37:29.496586+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from ipaddress import ip_interface


# revision identifiers, used by Alembic.
revision = '6e41203881b2'
down_revision = 'a3f3b07bb1aa'
branch_labels = None
depends_on = None


def pull_out_entries(rows):
    a_addresses = set()
    b_addresses = set()
    vips = set()
    for row in rows:
        if row['alias_v4address']:
            # v4address column always has the netmask bit
            a_addresses.add(ip_interface(f'{row["alias_v4address"]}/{row["alias_v4netmaskbit"]}'))
        elif row['alias_v6address']:
            # v6address column always has the netmask bit
            a_addresses.add(ip_interface(f'{row["alias_v6address"]}/{row["alias_v6netmaskbit"]}'))
        elif row['alias_vip']:
            vips.add(ip_interface(row['alias_vip']))
        elif row['alias_vipv6address']:
            vips.add(ip_interface(row['alias_vipv6address']))
        elif row['alias_v4address_b']:
            # on 12, netmask bit is written to db for _b address
            netmask = row['alias_v4netmaskbit'] if row['alias_v4netmaskbit'] else 32
            b_addresses.add(ip_interface(f'{row["alias_v4address_b"]}/{netmask}'))
        elif row['alias_v6address_b']:
            # on 12, IPv6 on HA systems isn't supported but it is on scale
            # but to be safe, we'll check to see if we're lucky and got the
            # prefix length
            netmask = row['alias_v6netmaskbit'] if row['alias_v6netmaskbit'] else 128
            b_addresses.add(ip_interface(f'{row["alias_v6address_b"]}/{netmask}'))

    return a_addresses, b_addresses, vips


def combine_entries(iface_id, a_addresses, b_addresses, vips):
    new_aliases = []
    new_alias = {
        'alias_interface_id': iface_id,
        'alias_address': '',
        'alias_address_b': '',
        'alias_netmask': 32,
        'alias_version': 4,
        'alias_vip': '',
    }
    for a_addr in a_addresses:
        alias = new_alias.copy()

        # controller A addresses
        alias['alias_address'] = str(a_addr.ip)
        alias['alias_netmask'] = int(a_addr.compressed.split('/')[-1])
        alias['alias_version'] = a_addr.ip.version

        # controller B addresses
        for b_addr in b_addresses:
            if b_addr.ip in a_addr.network:
                alias['alias_address_b'] = str(b_addr.ip)
                break

        # controller VIP addresses
        for v_addr in vips:
            if v_addr.ip in a_addr.network:
                alias['alias_vip'] = str(b_addr.ip)
                break

        # save the result
        new_aliases.append(alias)

    return new_aliases


def drop_and_create_new_table():
    op.drop_table('network_alias')

    op.create_table(
        'network_alias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('alias_interface_id', sa.Integer(), nullable=True),
        sa.Column('alias_address', sa.String(length=45), nullable=True),
        sa.Column('alias_version', sa.Integer(), nullable=False),
        sa.Column('alias_netmask', sa.Integer(), nullable=False),
        sa.Column('alias_address_b', sa.String(length=45), nullable=False),
        sa.Column('alias_vip', sa.String(length=45), nullable=False),
        sa.ForeignKeyConstraint(
            ['alias_interface_id'],
            ['network_interfaces.id'],
            name=op.f('fk_network_alias_alias_interface_id_network_interfaces'),
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_network_alias')),
        sqlite_autoincrement=True
    )
    with op.batch_alter_table('network_alias', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_network_alias_alias_interface_id'), ['alias_interface_id'], unique=False)


def upgrade():
    con = op.get_bind()
    new_aliases = []
    for iface_id, in con.execute(text('SELECT id from network_interfaces')).fetchall():
        rows = [row._asdict() for row in con.execute(text('SELECT * FROM network_alias WHERE alias_interface_id = :iface_id'), {'iface_id': iface_id}).fetchall()]
        a_addresses, b_addresses, vips = pull_out_entries(rows)
        new_aliases = combine_entries(iface_id, a_addresses, b_addresses, vips)

    drop_and_create_new_table()

    # now write our new values to newly created table
    for new_alias in new_aliases:
        alias = dict(new_alias)
        columns = ','.join(alias.keys())
        placeholders = ','.join([f":{key}" for key in alias.keys()])
        con.execute(text(f'INSERT INTO network_alias ({columns}) VALUES ({placeholders})'), alias)


def downgrade():
    pass
