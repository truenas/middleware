from collections import defaultdict

from middlewared.service import accepts, private, Service


class KubernetesService(Service):

    @accepts()
    async def events(self):
        """
        Returns events for kubernetes node.
        """
        return (await self.middleware.call('k8s.node.config')).get('events', [])

    @private
    async def get_events_of_resource_type(self, resource, resource_uids=None):
        assert resource in ('StatefulSet', 'Pod', 'Deployment')
        events = defaultdict(list)
        resource_uids = resource_uids or []
        filters = []
        if resource_uids:
            filters.append(['involved_object.uid', 'in', resource_uids])
        for event in await self.middleware.call(
            'k8s.event.query', filters, {'extra': {'field_selector': f'involvedObject.kind={resource}'}}
        ):
            events[event['involved_object']['uid']].append(event)

        return events
