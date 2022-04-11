class ServiceInterface:
    name = NotImplemented

    etc = []
    restartable = False  # Implements `restart` method instead of `stop` + `start`
    reloadable = False  # Implements `reload` method

    def __init__(self, middleware):
        self.middleware = middleware

    async def get_state(self):
        raise NotImplementedError

    async def start(self):
        raise NotImplementedError

    async def before_start(self):
        pass

    async def after_start(self):
        pass

    async def stop(self):
        raise NotImplementedError

    async def before_stop(self):
        pass

    async def after_stop(self):
        pass

    async def restart(self):
        raise NotImplementedError

    async def before_restart(self):
        pass

    async def after_restart(self):
        pass

    async def reload(self):
        raise NotImplementedError

    async def before_reload(self):
        pass

    async def after_reload(self):
        pass


class IdentifiableServiceInterface:
    async def identify(self, procname):
        raise NotImplementedError
