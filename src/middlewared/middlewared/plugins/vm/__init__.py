async def setup(middleware):
    middleware.event_register('vm.query', 'Sent on VM state changes.')
