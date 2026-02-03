from sqlalchemy.ext.declarative import declared_attr

import middlewared.sqlalchemy as sa


class CloudTaskModelMixin:
    id = sa.Column(sa.Integer(), primary_key=True)
    description = sa.Column(sa.String(150))
    path = sa.Column(sa.String(255))
    dataset = sa.Column(sa.String(255), nullable=True)
    relative_path = sa.Column(sa.String(255), nullable=True)

    @declared_attr
    def credential_id(cls):
        return sa.Column(sa.ForeignKey("system_cloudcredentials.id"), index=True)

    attributes = sa.Column(sa.JSON())
    minute = sa.Column(sa.String(100), default="00")
    hour = sa.Column(sa.String(100), default="*")
    daymonth = sa.Column(sa.String(100), default="*")
    month = sa.Column(sa.String(100), default="*")
    dayweek = sa.Column(sa.String(100), default="*")
    pre_script = sa.Column(sa.Text())
    post_script = sa.Column(sa.Text())
    snapshot = sa.Column(sa.Boolean())
    include = sa.Column(sa.JSON(list))
    exclude = sa.Column(sa.JSON(list))
    args = sa.Column(sa.Text())
    enabled = sa.Column(sa.Boolean(), default=True)
    job = sa.Column(sa.JSON(None))
