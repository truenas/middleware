import pytest

from middlewared.plugins.apps.schema_construction_utils import generate_pydantic_model
from middlewared.plugins.apps.schema_validation import validate_image_overrides
from middlewared.service import ValidationErrors


def test_framework_image_override_model_accepts_structured_entries():
    model = generate_pydantic_model([], 'app_create', {'image_overrides': [{
        'selector': 'image',
        'registry': 'mirror.example:5000',
        'digest': 'sha256:' + 'a' * 64,
    }]})
    value = model.model_validate({'image_overrides': [{
        'selector': 'image',
        'registry': 'mirror.example:5000',
        'digest': 'sha256:' + 'a' * 64,
    }]})
    assert value.image_overrides[0].selector == 'image'


@pytest.mark.parametrize('override', [
    {'registry': 42},
    {'registry': None},
    {'registry': 'https://mirror.example'},
    {'registry': 'mirror/path'},
    {'digest': 'sha256:short'},
    {'tag': 'new', 'digest': 'sha256:' + 'a' * 64},
    {'unknown': 'value'},
])
def test_image_override_validator_rejects_invalid_values(override):
    errors = ValidationErrors()
    validate_image_overrides(errors, {'image_overrides': {'image': override}})
    assert errors.errors


def test_image_override_validator_accepts_registry_port_and_digest():
    errors = ValidationErrors()
    validate_image_overrides(errors, {'image_overrides': {
        'image': {'registry': 'mirror.example:5000', 'digest': 'sha256:' + 'b' * 64},
    }})
    assert not errors.errors
