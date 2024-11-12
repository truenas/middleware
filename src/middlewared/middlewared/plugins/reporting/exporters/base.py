class Export:

    NAME = NotImplementedError()
    SCHEMA_MODEL = NotImplementedError()

    @staticmethod
    async def validate_config(data):
        raise NotImplementedError()
