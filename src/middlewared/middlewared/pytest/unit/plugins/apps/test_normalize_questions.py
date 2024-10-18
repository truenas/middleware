import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService, REF_MAPPING
from middlewared.pytest.unit.middleware import Middleware
from middlewared.schema import Dict, List


@pytest.mark.parametrize('question_attr, ref, value, update', [
    (
        Dict(),
        'definitions/certificate',
        {'attr1': 'some_value'},
        False
    ),
    (
        Dict(),
        'normalize/acl',
        {'attr1': 'some_value'},
        False
    ),
    (
        Dict(),
        'normalize/acl',
        {'attr1': 'some_value'},
        True
    ),
    (
        Dict(),
        'definitions/certificate',
        None,
        False
    )
])
@pytest.mark.asyncio
async def test_normalize_question(question_attr, ref, value, update):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    middleware[f'app.schema.normalize_{REF_MAPPING[ref]}'] = lambda *args: value
    question_attr.ref = [ref]
    result = await app_schema_obj.normalize_question(question_attr, value, update, '', '')
    assert result == value


@pytest.mark.parametrize('question_attr, ref, value, update', [
    (
        List(
            items=[
                Dict('question1', additional_attrs=True),
                Dict('question2', additional_attrs=True),
                Dict('question3', additional_attrs=True),
            ]
        ),
        'definitions/certificate',
        [
            {'question1': 'val1'},
            {'question2': 'val2'},
            {'question3': 'val3'}
        ],
        False
    ),
])
@pytest.mark.asyncio
async def test_normalize_question_List(question_attr, ref, value, update):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    middleware[f'app.schema.normalize_{REF_MAPPING[ref]}'] = lambda *args: value
    for attr in question_attr.items:
        attr.ref = [ref]
    question_attr.ref = [ref]

    result = await app_schema_obj.normalize_question(question_attr, value, update, '', '')
    assert result == value
