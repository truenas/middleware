import types

from middlewared.job import Job


class Method:
    def __init__(self, middleware: "Middleware", name: str):
        self.middleware = middleware
        self.name = name

    async def call(self, app: "RpcWebSocketApp", params):
        serviceobj, methodobj = self.middleware.get_method(self.name)

        await self.middleware.authorize_method_call(app, self.name, methodobj, params)

        if mock := self.middleware._mock_method(self.name, params):
            methodobj = mock

        result = await self.middleware.call_with_audit(self.name, serviceobj, methodobj, params, app)
        if isinstance(result, Job):
            result = result.id
        elif isinstance(result, types.GeneratorType):
            result = list(result)
        elif isinstance(result, types.AsyncGeneratorType):
            result = [i async for i in result]

        return result

    def dump_args(self, params):
        return self.middleware.dump_args(params, method_name=self.name)
