import pytest
from pydantic import BaseModel, ValidationError

from middlewared.plugins.apps.schema_construction_utils import _make_index_validator


class SimpleModel(BaseModel):
    value: int
    name: str


class ExceptionWithErrors:
    def errors(self):
        return [
            {'loc': ('field1',), 'msg': 'Test error', 'type': 'test_error'}
        ]


def test_pydantic_validation_error_ctx():
    """Test Pydantic ValidationError gets ctx field added"""
    validator = _make_index_validator([SimpleModel], 'TestModel')

    # Invalid data to trigger Pydantic ValidationError
    with pytest.raises(ValidationError) as exc_info:
        validator([{'value': 'not_int', 'name': 'test'}])

    # Verify ctx field exists
    errors = exc_info.value.errors()
    assert all('ctx' in err and 'error' in err['ctx'] for err in errors)


def test_exception_with_errors_method():
    """Test exceptions with errors() method get ctx field"""
    validator = _make_index_validator([SimpleModel], 'TestModel')

    # Patch to raise our custom exception
    original_init = SimpleModel.__init__
    SimpleModel.__init__ = lambda self, **data: (_ for _ in ()).throw(ExceptionWithErrors())

    try:
        with pytest.raises(ValidationError) as exc_info:
            validator([{'value': 1, 'name': 'test'}])

        errors = exc_info.value.errors()
        assert all('ctx' in err and 'error' in err['ctx'] for err in errors)
    finally:
        SimpleModel.__init__ = original_init


def test_generic_exception():
    """Test generic exceptions get ctx field"""
    validator = _make_index_validator([SimpleModel], 'TestModel')

    # Patch to raise generic exception
    original_init = SimpleModel.__init__
    SimpleModel.__init__ = lambda self, **data: (_ for _ in ()).throw(RuntimeError("Test error"))

    try:
        with pytest.raises(ValidationError) as exc_info:
            validator([{'value': 1, 'name': 'test'}])

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert 'ctx' in errors[0]
        assert errors[0]['ctx']['error'] == "Test error"
    finally:
        SimpleModel.__init__ = original_init
