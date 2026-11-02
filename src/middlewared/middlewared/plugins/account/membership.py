from __future__ import annotations

import middlewared.sqlalchemy as sa

__all__ = ("GroupMembershipModel",)


class GroupMembershipModel(sa.Model):
    """Join table between ``UserModel`` and ``GroupModel``.

    It lives apart from both so that either side's relationship can reference the table
    without one CRUD module having to import the other.
    """

    __tablename__ = "account_bsdgroupmembership"

    id = sa.Column(sa.Integer(), primary_key=True)
    bsdgrpmember_group_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdgroups.id", ondelete="CASCADE"))
    bsdgrpmember_user_id = sa.Column(sa.Integer(), sa.ForeignKey("account_bsdusers.id", ondelete="CASCADE"))
