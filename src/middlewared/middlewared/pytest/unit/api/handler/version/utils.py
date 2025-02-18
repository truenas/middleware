from middlewared.api.base import BaseModel
from middlewared.api.base.handler.model_provider import ModelProvider


class TestModelProvider(ModelProvider):
    def __init__(self, models: dict[str, type[BaseModel]]):
        self.models = models

    async def get_model(self, name: str) -> type[BaseModel]:
        return self.models[name]
