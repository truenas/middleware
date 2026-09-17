import pytest

from middlewared.api.current import QueryOptions, ZFSResourceQueryArgs
from middlewared.plugins.zfs.resource import ZFSResourceService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors


def test_query_keeps_typed_args():
    assert ZFSResourceService.query.new_style_accepts is ZFSResourceQueryArgs


def test_get_instance_is_wrapped_with_string_id():
    assert ZFSResourceService.get_instance.new_style_accepts.model_fields["id"].annotation is str


@pytest.mark.asyncio
async def test_get_instance_rejects_private_extra():
    svc = ZFSResourceService(Middleware())
    with pytest.raises(ValidationErrors) as exc_info:
        await svc.get_instance("tank/.system", QueryOptions(extra={"exclude_internal_paths": False}))

    assert len(exc_info.value.errors) == 1
    assert exc_info.value.errors[0].attribute == "options.extra.exclude_internal_paths"
    assert exc_info.value.errors[0].errmsg == "Extra inputs are not permitted"
