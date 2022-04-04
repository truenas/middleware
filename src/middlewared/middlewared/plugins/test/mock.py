from middlewared.service import CallError, Service


class TestService(Service):
    class Config:
        private = True

    async def set_mock(self, name, description):
        if isinstance(description, str):
            exec(description)
            try:
                method = locals()["mock"]
            except KeyError:
                raise CallError("Your mock declaration must include `def mock` or `async def mock`")
        elif isinstance(description, dict):
            keys = set(description.keys())
            if keys == {"return_value"}:
                def method(*args, **kwargs):
                    return description["return_value"]
            else:
                raise CallError("Invalid mock declaration")
        else:
            raise CallError("Invalid mock declaration")

        self.middleware.set_mock(name, method)

    async def remove_mock(self, name):
        self.middleware.remove_mock(name)

    # Dummy methods to mock for internal infrastructure testing (i.e. jobs manager)

    async def test1(self):
        pass

    async def test2(self):
        pass
