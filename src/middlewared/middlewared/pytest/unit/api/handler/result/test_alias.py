from pydantic import Field

from middlewared.api.base import BaseModel
from middlewared.api.base.handler.result import serialize_result


def test_dump_by_alias():
    class AliasModel(BaseModel):
        field1_: int = Field(alias='field1')
        field2: str
        field3_: bool = Field(alias='field3', default=False)

    class AliasModelResult(BaseModel):
        result: AliasModel

    result = serialize_result(AliasModelResult, {'field1': 1, 'field2': 'two'}, True, False)
    assert result == {'field1': 1, 'field2': 'two', 'field3': False}
