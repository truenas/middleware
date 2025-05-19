import unittest

import pytest

from middlewared.api import api_method
from middlewared.api.base import BaseModel


class MethodArgs(BaseModel): ...


class MethodResult(BaseModel):
    result: None


@pytest.mark.parametrize("kwargs, error", [
    (
        {"private": True, "roles": ["READONLY_ADMIN"]},
        "Cannot set roles, no authorization, or no authentication on private methods."
    ),
    (
        {"roles": ["READONLY_ADMIN"], "authorization_required": False},
        "Authentication and authorization must be enabled in order to use roles."
    ),
    (
        {"authorization_required": False, "authentication_required": False},
        "Either authentication or authorization may be disabled, but not both simultaneously."
    ),
    (
        {},
        "method: Role definition is required for public API endpoints"
    )
])
@unittest.mock.patch("middlewared.api.base.decorator.check_model_module")
def test_bad_api_method_args(check_model_module, kwargs, error):
    with pytest.raises(ValueError, match=error):
        @api_method(MethodArgs, MethodResult, **kwargs)
        def method(): ...


@pytest.mark.parametrize("kwargs, attr_name, attr_value", [
    ({"private": True}, "_private", True),
    ({"roles": ["READONLY_ADMIN"]}, "roles", ["READONLY_ADMIN"]),
    ({"authorization_required": False}, "_no_authz_required", True),
    ({"authentication_required": False}, "_no_auth_required", True),
])
@unittest.mock.patch("middlewared.api.base.decorator.check_model_module")
def test_api_method_args(check_model_module, kwargs, attr_name, attr_value):
    @api_method(MethodArgs, MethodResult, **kwargs)
    def method(): ...

    assert getattr(method, attr_name) == attr_value
