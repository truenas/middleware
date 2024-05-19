import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, List, Str
from middlewared.service import CRUDService
from middlewared.validators import Match


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    repository = sa.Column(sa.Text(), nullable=False)
    branch = sa.Column(sa.String(255), nullable=False)
    builtin = sa.Column(sa.Boolean(), nullable=False, default=False)
    preferred_trains = sa.Column(sa.JSON(list))


class CatalogService(CRUDService):

    class Config:
        datastore = 'services.catalog'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        namespace = 'catalog'

    ENTRY = Dict(
        'catalog_entry',
        Bool('builtin'),
        List('preferred_trains'),
        Str(
            'label', required=True, validators=[Match(
                r'^\w+[\w.-]*$',
                explanation='Label must start with an alphanumeric character and can include dots and dashes.'
            )],
            max_length=60,
        ),
        Str('repository', required=True, empty=False),
        Str('branch', required=True, empty=False),
        Str('location', required=True),
        Str('id', required=True),
    )
