import pytest
from unittest.mock import patch
from middlewared.api.base import BaseModel
from middlewared.api import api_method
from middlewared.api.current import QueryArgs
from middlewared.service import Service


# Mock check_model_module to allow models in test file
@patch('middlewared.api.base.decorator.check_model_module')
def test_valid_service_method_names(mock_check_model):
    """Test that valid service method names pass validation during class creation"""
    class TestGetDataArgs(BaseModel):
        filter: str = ''

    class TestGetDataResult(BaseModel):
        result: dict

    class TestUpdateDataArgs(BaseModel):
        data: dict

    class TestUpdateDataResult(BaseModel):
        result: dict

    class TestCreateArgs(BaseModel):
        data: dict

    class TestCreateResult(BaseModel):
        result: dict

    class TestService(Service):
        class Config:
            namespace = 'test'

        @api_method(
            TestGetDataArgs,
            TestGetDataResult,
            roles=['READONLY_ADMIN']
        )
        def get_data(self):
            return {'data': 'test'}

        @api_method(
            TestUpdateDataArgs,
            TestUpdateDataResult,
            roles=['FULL_ADMIN']
        )
        def update_data(self):
            return {'status': 'updated'}

        @api_method(
            TestCreateArgs,
            TestCreateResult,
            roles=['FULL_ADMIN']
        )
        def do_create(self):
            return {'status': 'created'}


@patch('middlewared.api.base.decorator.check_model_module')
def test_invalid_service_method_names(mock_check_model):
    """Test that invalid service method names raise RuntimeError during class creation"""
    class WrongNameArgs(BaseModel):
        filter: str = ''

    class WrongNameResult(BaseModel):
        result: dict

    with pytest.raises(RuntimeError, match="has incorrect accepts class name"):
        class InvalidService(Service):
            class Config:
                namespace = 'invalid'

            @api_method(
                WrongNameArgs,
                WrongNameResult,
                roles=['READONLY_ADMIN']
            )
            def get_data(self):
                return {'data': 'test'}


@patch('middlewared.api.base.decorator.check_model_module')
def test_service_with_query_args(mock_check_model):
    """Test that services using QueryArgs pass validation during class creation"""
    class TestServiceWithQueryArgsGetDataResult(BaseModel):
        result: dict

    class TestServiceWithQueryArgs(Service):
        class Config:
            namespace = 'test_query'

        @api_method(
            QueryArgs,
            TestServiceWithQueryArgsGetDataResult,
            roles=['READONLY_ADMIN']
        )
        def get_data(self):
            return {'data': 'test'}


@patch('middlewared.api.base.decorator.check_model_module')
def test_service_with_private_method(mock_check_model):
    """Test that private methods are skipped during validation on class creation"""
    class TestServiceWithPrivateMethodGetDataArgs(BaseModel):
        filter: str = ''

    class TestServiceWithPrivateMethodGetDataResult(BaseModel):
        result: dict

    class TestServiceWithPrivateMethod(Service):
        class Config:
            namespace = 'test_private'

        @api_method(
            TestServiceWithPrivateMethodGetDataArgs,
            TestServiceWithPrivateMethodGetDataResult,
            private=True
        )
        def _get_data(self):
            return {'data': 'test'}
