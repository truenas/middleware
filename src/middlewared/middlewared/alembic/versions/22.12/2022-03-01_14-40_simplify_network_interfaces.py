"""simplify network_interfaces table

Revision ID: a2ae33484fed
Revises: 4c852b54dfa1
Create Date: 2022-03-01 14:40:25.351989+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a2ae33484fed'
down_revision = '4c852b54dfa1'
branch_labels = None
depends_on = None


def create_new_entries(old_entry):
    new_entry = {}
    alias_entry = {}
    if old_entry['int_ipv4address'] and old_entry['int_ipv6address']:
        # this shouldn't happen but we'll play it safe
        # we'll write the ipv4 address to the network_interface table
        new_entry['id'] = old_entry['id']
        new_entry['int_address'] = old_entry['int_ipv4address']
        new_entry['int_address_b'] = old_entry['int_ipv4address_b']
        new_entry['int_version'] = 4
        new_entry['int_netmask'] = int(old_entry['int_v4netmaskbit']) if old_entry['int_v4netmaskbit'] else 32

        # we'll write the ipv6 address to the network_alias table
        alias_entry['alias_interface_id'] = old_entry['id']
        alias_entry['alias_address'] = old_entry['int_ipv6address']
        alias_entry['alias_address_b'] = old_entry['int_ipv6address_b']
        alias_entry['alias_vip'] = old_entry['int_vipv6address'] or ''
        alias_entry['alias_version'] = 6
        alias_entry['alias_netmask'] = int(old_entry['int_v6netmaskbit']) if old_entry['int_v6netmaskbit'] else 128
    elif old_entry['int_ipv4address']:
        new_entry['id'] = old_entry['id']
        new_entry['int_address'] = old_entry['int_ipv4address']
        new_entry['int_address_b'] = old_entry['int_ipv4address_b']
        new_entry['int_version'] = 4
        new_entry['int_netmask'] = int(old_entry['int_v4netmaskbit']) if old_entry['int_v4netmaskbit'] else 32
    elif old_entry['int_ipv6address']:
        new_entry['id'] = old_entry['id']
        new_entry['int_address'] = old_entry['int_ipv6address']
        new_entry['int_address_b'] = old_entry['int_ipv6address_b']
        new_entry['int_vip'] = old_entry['int_vipv6address']
        new_entry['int_version'] = 6
        new_entry['int_netmask'] = int(old_entry['int_v6netmaskbit']) if old_entry['int_v6netmaskbit'] else 128
    return new_entry, alias_entry


def upgrade():
    con = op.get_bind()
    new_entries = []
    for old_entry in map(dict, con.execute(text('SELECT * FROM network_interfaces')).fetchall()):
        new_entries.append(create_new_entries(old_entry))

    # add new columns
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.add_column(sa.Column('int_address', sa.String(length=45), server_default='', nullable=False))
        batch_op.add_column(sa.Column('int_address_b', sa.String(length=45), server_default='', nullable=True))
        batch_op.add_column(sa.Column('int_netmask', sa.Integer(), server_default='', nullable=False))
        batch_op.add_column(sa.Column('int_version', sa.Integer(), server_default='', nullable=False))

    # update new columns
    for new_entry, alias_entry in new_entries:
        if new_entry:
            _id = new_entry.pop('id')
            for column, value in new_entry.items():
                con.execute(text(f'UPDATE network_interfaces SET {column} = :value WHERE id = :id'), {'value': value, 'id': _id})
        if alias_entry:
            columns = ','.join(alias_entry.keys())
            placeholders = ','.join([f":{key}" for key in alias_entry.keys()])
            con.execute(text(f'INSERT INTO network_alias ({columns}) VALUES ({placeholders})'), alias_entry)

    # remove old columns
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.drop_column('int_ipv6address_b')
        batch_op.drop_column('int_ipv6address')
        batch_op.drop_column('int_vipv6address')
        batch_op.drop_column('int_ipv4address')
        batch_op.drop_column('int_v4netmaskbit')
        batch_op.drop_column('int_v6netmaskbit')
        batch_op.drop_column('int_ipv4address_b')


def downgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.add_column(sa.Column('int_ipv4address_b', sa.VARCHAR(length=42), nullable=False))
        batch_op.add_column(sa.Column('int_v6netmaskbit', sa.VARCHAR(length=3), nullable=False))
        batch_op.add_column(sa.Column('int_v4netmaskbit', sa.VARCHAR(length=3), nullable=False))
        batch_op.add_column(sa.Column('int_ipv4address', sa.VARCHAR(length=42), nullable=False))
        batch_op.add_column(sa.Column('int_vipv6address', sa.VARCHAR(length=45), nullable=True))
        batch_op.add_column(sa.Column('int_ipv6address', sa.VARCHAR(length=45), nullable=False))
        batch_op.add_column(sa.Column('int_ipv6address_b', sa.VARCHAR(length=45), nullable=False))
        batch_op.drop_column('int_version')
        batch_op.drop_column('int_netmask')
        batch_op.drop_column('int_address_b')
        batch_op.drop_column('int_address')
