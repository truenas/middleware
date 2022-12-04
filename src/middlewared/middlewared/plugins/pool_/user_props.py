from middlewared.schema import Dict, Str
from middlewared.service import accepts, CRUDService, filterable, ValidationErrors
from middlewared.utils import filter_list
from middlewared.validators import Match


class PoolDatasetUserPropService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'pool.dataset.userprop'
        cli_namespace = 'storage.dataset.user_prop'

    ENTRY = Dict(
        'pool_dataset_userprop_entry',
        Str('id', required=True),
        Dict('properties', additional_attrs=True, required=True),
    )

    @filterable
    def query(self, filters, options):
        """
        Query all user properties for ZFS datasets.
        """
        return filter_list(
            [
                {k: d[k] for k in ('id', 'properties')} for d in
                (self.middleware.call_sync('zfs.dataset.query', [], {
                    'extra': {'user_properties': True, 'properties': []}
                }))
            ], filters, options
        )

    async def __common_validation(self, dataset, data, schema, update=False):
        verrors = ValidationErrors()
        exists = data['name'] in dataset['properties']
        if (exists and not update) or (not exists and update):
            if update:
                msg = f'{data["name"]} does not exist in {dataset["id"]} user properties'
            else:
                msg = f'{data["name"]} exists in {dataset["id"]} user properties'
            verrors.add(f'{schema}.property.name', msg)

        return verrors

    @accepts(
        Dict(
            'dataset_user_prop_create',
            Str('id', required=True, empty=False),
            Dict(
                'property',
                Str('name', required=True, validators=[Match(r'.*:.*')]),
                Str('value', required=True),
            )
        )
    )
    async def do_create(self, data):
        """
        Create a user property for a given `id` dataset.
        """
        dataset = await self.get_instance(data['id'])
        verrors = await self.__common_validation(dataset, data['property'], 'dataset_user_prop_create')
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', data['id'], {
                'properties': {data['property']['name']: {'value': data['property']['value']}}
            }
        )

        return await self.get_instance(data['id'])

    @accepts(
        Str('id'),
        Dict(
            'dataset_user_prop_update',
            Str('name', required=True),
            Str('value', required=True),
        )
    )
    async def do_update(self, id, data):
        """
        Update `dataset_user_prop_update.name` user property for `id` dataset.
        """
        dataset = await self.get_instance(id)
        verrors = await self.__common_validation(dataset, data, 'dataset_user_prop_update', True)
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', id, {
                'properties': {data['name']: {'value': data['value']}}
            }
        )

        return await self.get_instance(id)

    @accepts(
        Str('id'),
        Dict(
            'dataset_user_prop_delete',
            Str('name', required=True),
        )
    )
    async def do_delete(self, id, options):
        """
        Delete user property `dataset_user_prop_delete.name` for `id` dataset.
        """
        dataset = await self.get_instance(id)
        verrors = await self.__common_validation(dataset, options, 'dataset_user_prop_delete', True)
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', id, {
                'properties': {options['name']: {'source': 'INHERIT'}}
            }
        )
        return True
