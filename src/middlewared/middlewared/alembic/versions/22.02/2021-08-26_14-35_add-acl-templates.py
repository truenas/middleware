"""Add ACL templates

Revision ID: a05844ffb381
Revises: 0963604b62f9
Create Date: 2021-08-26 14:35:02.063560+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import enum
import json


# revision identifiers, used by Alembic.
revision = 'a05844ffb381'
down_revision = '0963604b62f9'
branch_labels = None
depends_on = None

class ACLDefault(enum.Enum):
    NFS4_OPEN = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        }
    ]}
    NFS4_RESTRICTED = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
    ]}
    NFS4_HOME = {'visible': True, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'TRAVERSE'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        },
    ]}
    NFS4_DOMAIN_HOME = {'visible': False, 'acl': [
        {
            'tag': 'owner@',
            'id': None,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        },
        {
            'tag': 'group@',
            'id': None,
            'perms': {'BASIC': 'MODIFY'},
            'flags': {
                'DIRECTORY_INHERIT': True,
                'INHERIT_ONLY': True,
                'NO_PROPAGATE_INHERIT': True
            },
            'type': 'ALLOW'
        },
        {
            'tag': 'everyone@',
            'id': None,
            'perms': {'BASIC': 'TRAVERSE'},
            'flags': {'BASIC': 'NOINHERIT'},
            'type': 'ALLOW'
        }
    ]}
    POSIX_OPEN = {'visible': True, 'acl': [
        {
            'default': True, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        }
    ]}
    POSIX_RESTRICTED = {'visible': True, 'acl': [
        {
            'default': True, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": False, "WRITE": False, "EXECUTE": False},
        },
        {
            'default': False, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": False, "WRITE": False, "EXECUTE": False},
        }
    ]}
    POSIX_HOME = {'visible': True, 'acl': [
        {
            'default': True, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': True, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": False, "WRITE": False, "EXECUTE": False},
        },
        {
            'default': False, 'tag': 'USER_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'GROUP_OBJ', 'id': -1,
            'perms': {"READ": True, "WRITE": True, "EXECUTE": True},
        },
        {
            'default': False, 'tag': 'OTHER', 'id': -1,
            'perms': {"READ": True, "WRITE": False, "EXECUTE": True},
        }
    ]}


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('filesystem_acltemplate',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('acltemplate_name', sa.String(length=120), nullable=False),
    sa.Column('acltemplate_acltype', sa.String(length=255), nullable=False),
    sa.Column('acltemplate_acl', sa.TEXT(), nullable=False),
    sa.Column('acltemplate_builtin', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_filesystem_acltemplate')),
    sa.UniqueConstraint('acltemplate_name', name=op.f('uq_filesystem_acltemplate_acltemplate_name')),
    sqlite_autoincrement=True
    )

    conn = op.get_bind()

    for i in ACLDefault:
        acltype = "NFS4" if i.name.split("_")[0] == "NFS4" else "POSIX1E"
        entry = {
            "acltemplate_name": i.name,
            "acltemplate_acltype": acltype,
            "acltemplate_acl": json.dumps(i.value["acl"]),
            "acltemplate_builtin": True,
        }
        columns = ','.join(entry.keys())
        placeholders = ','.join([f":{key}" for key in entry.keys()])
        conn.execute(
            text(f"INSERT INTO filesystem_acltemplate ({columns}) VALUES ({placeholders})"),
            entry
        )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('filesystem_acltemplate')
    # ### end Alembic commands ###
