class Export:

    NAME = NotImplementedError()
    SCHEMA = NotImplementedError()

    @staticmethod
    async def validate_config(data):
        raise NotImplementedError()
