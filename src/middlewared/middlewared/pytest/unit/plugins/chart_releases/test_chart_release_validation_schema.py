import pytest
from unittest.mock import patch

from middlewared.service_exception import ValidationErrors
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware


ChartReleaseService = load_compound_service('chart.release')

schema_variables = ['appVolumeMounts', 'transcode', 'hostPath']
QUESTION_DATA = {
    'schema': {
        'questions': [{
            'variable': 'appVolumeMounts',
            'schema': {
                'type': 'dict',
                'attrs': [{
                    'variable': 'transcode',
                    'schema': {
                        'type': 'dict',
                        'attrs': [{
                            'variable': 'hostPath',
                            'schema': {
                                'type': 'hostpath',
                                'required': True,
                                '$ref': [
                                    'validations/lockedHostPath'
                                ],
                            }
                        }]
                    }
                }]
            }
        }]
    }
}

values = {'appVolumeMounts': {'transcode': {'hostPath': '/mnt/evo'}}}


@pytest.mark.asyncio
async def test_create_schema_formation():
    m = Middleware()
    chart_release_svc = ChartReleaseService(m)

    m['chart.release.validate_locked_host_path'] = chart_release_svc.validate_locked_host_path
    m['pool.dataset.path_in_locked_datasets'] = lambda *args: True
    with patch('middlewared.schema.HostPath.validate') as validation:
        validation.return_value = ValidationErrors()
        with pytest.raises(ValidationErrors) as verrors:
            await chart_release_svc.validate_values(QUESTION_DATA, values, False)
    assert 'chart_release_create.appVolumeMounts.transcode.hostPath' in verrors.value
