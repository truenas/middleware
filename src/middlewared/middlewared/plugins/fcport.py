import middlewared.sqlalchemy as sa


class FCPortModel(sa.Model):
    __tablename__ = 'services_fibrechanneltotarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    fc_port = sa.Column(sa.String(10))
    fc_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), nullable=True, index=True)
