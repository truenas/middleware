from pydantic import Field

from middlewared.api.base import BaseModel


def test_dump_by_alias():
    class AliasModel(BaseModel):
        field1_: int = Field(..., alias='field1')
        field2: str
        field3_: bool = Field(alias='field3', default=False)

    class AliasModelResult(BaseModel):
        result: AliasModel

    result = {'field1': 1, 'field2': 'two'}
    result_model = AliasModelResult(result=result)

    assert result_model.model_dump()['result'] == {'field1_': 1, 'field2': 'two', 'field3_': False}
    assert result_model.model_dump(by_alias=True)['result'] == {'field1': 1, 'field2': 'two', 'field3': False}
