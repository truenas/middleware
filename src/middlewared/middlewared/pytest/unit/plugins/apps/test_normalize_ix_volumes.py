import pytest

from middlewared.plugins.apps.ix_apps.path import get_app_volume_path
from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('attr, value, complete_config, context', [
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [{'type': 'ALLOW', 'permissions': 'write'}],
                'path': '/mnt/data'
            }
        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {'actions': [], 'app': {'name': 'test_app'}}
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }
        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {'actions': [], 'app': {'name': 'test_app'}}
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }

        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {
            'actions': [
                {
                    'method': 'update_volumes',
                    'args': [[
                        {
                            'name': 'volume_1'
                        }
                    ]]
                }
            ],
            'app': {'name': 'test_app'}
        }
    ),
    (
        {'schema': {'type': 'dict'}},
        {
            'dataset_name': 'volume_1',
            'properties': {'prop_key': 'prop_value'},
            'acl_entries': {
                'entries': [],
                'path': ''
            }

        },
        {
            'ix_volumes': {
                'volume_1': ''
            }
        },
        {
            'actions': [
                {
                    'method': 'update_volumes',
                    'args': [[
                        {
                            'name': 'volume_2'
                        }
                    ]]
                }
            ],
            'app': {'name': 'test_app'}
        }
    ),
])
@pytest.mark.asyncio
async def test_normalize_ix_volumes(attr, value, complete_config, context):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    result = await app_schema_obj.normalize_ix_volume(attr, value, complete_config, context)
    assert len(context['actions']) > 0
    assert value['dataset_name'] in [v['name'] for v in context['actions'][0]['args'][-1]]
    assert result == value

    acl_action = next((a for a in context['actions'] if a['method'] == 'apply_acls'), None)
    if value['acl_entries']['entries']:
        # The path here is stamped by normalization and always points inside the app's own volume
        # directory, so the ACL apply which gets queued for it has to come out forced
        assert acl_action is not None
        assert acl_action['args'][0][value['acl_entries']['path']]['options']['force'] is True
    else:
        assert acl_action is None


@pytest.mark.parametrize('options', [
    # An explicitly disabled force flag on the app's own volume is overridden rather than
    # allowed to block the ACL apply
    {'force': False},
    {'force': True},
    # An absent options key has to be created so the flag can be recorded at all
    None,
])
@pytest.mark.asyncio
async def test_normalize_ix_volume_forces_acl_on_own_volume(options):
    app_schema_obj = AppSchemaService(Middleware())
    acl_entries = {'entries': [{'type': 'ALLOW', 'permissions': 'read'}], 'path': ''}
    if options is not None:
        acl_entries['options'] = options
    value = {'dataset_name': 'data', 'acl_entries': acl_entries}
    context = {'actions': [], 'app': {'name': 'test_app'}}

    await app_schema_obj.normalize_ix_volume({'schema': {'type': 'dict'}}, value, {'ix_volumes': {}}, context)

    host_path = f'{get_app_volume_path("test_app")}/data'
    assert acl_entries['path'] == host_path
    assert acl_entries['options'] == {'force': True}
    acl_action = next(a for a in context['actions'] if a['method'] == 'apply_acls')
    # The queued action has to hold the very same dict which gets persisted, otherwise the stored
    # config and the ACL which was actually applied would disagree
    assert acl_action['args'][0][host_path] is acl_entries


# `dataset_name` is not validated as a path anywhere, so an absolute or `..`-laden one steers the volume
# host path out of the app's own tree. Forcing there would be forcing over data which is not the app's, so
# the flag has to be left exactly as it was submitted and the escaped path queued unforced. Note that the
# host path is built with os.path.join, which does not collapse `..`, so the queued path is the literal
# un-collapsed string even though the containment check itself normalizes before comparing.
@pytest.mark.parametrize('dataset_name, escaped_path', [
    ('/mnt/tank/data', '/mnt/tank/data'),
    ('../other-app/media', f'{get_app_volume_path("test_app")}/../other-app/media'),
])
@pytest.mark.asyncio
async def test_normalize_ix_volume_does_not_force_escaped_dataset_name(dataset_name, escaped_path):
    app_schema_obj = AppSchemaService(Middleware())
    acl_entries = {
        'entries': [{'type': 'ALLOW', 'permissions': 'read'}],
        # The path carried in a stored config points at the app's own volume directory
        'path': f'{get_app_volume_path("test_app")}/data',
        'options': {'force': False},
    }
    value = {'dataset_name': dataset_name, 'acl_entries': acl_entries}
    context = {'actions': [], 'app': {'name': 'test_app'}}

    await app_schema_obj.normalize_ix_volume({'schema': {'type': 'dict'}}, value, {'ix_volumes': {}}, context)

    assert acl_entries['path'] == escaped_path
    assert acl_entries['options']['force'] is False
    acl_action = next(a for a in context['actions'] if a['method'] == 'apply_acls')
    assert acl_action['args'][0][escaped_path] is acl_entries
    assert all(queued['options']['force'] is False for queued in acl_action['args'][0].values())
