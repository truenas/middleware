from middlewared.plugins.interface.netif import netif
from middlewared.schema import Int
from middlewared.service import accepts, CallError, CRUDService, filterable


class IPRulesService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        return [rule.__getstate__() for rule in netif.IPRules()]

    @accepts(Int('priority'))
    async def do_delete(self, priority):
        rule = next((r for r in netif.IPRules() if r.priority == priority), None)
        if not rule:
            raise CallError(f'Unable to find any IP rule with priority {priority}')

        rule.delete()
