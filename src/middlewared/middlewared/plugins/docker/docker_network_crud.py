from __future__ import annotations

from typing import Any

from middlewared.api.current import DockerNetworkEntry, QueryOptions
from middlewared.plugins.apps.ix_apps.docker.networks import list_networks
from middlewared.service import CRUDServicePart
from middlewared.service_exception import InstanceNotFound
from middlewared.utils.filter_list import filter_list

from .state_management import validate_state


class DockerNetworkServicePart(CRUDServicePart[DockerNetworkEntry, str]):
    _entry = DockerNetworkEntry

    async def query(  # type: ignore[override]
        self, filters: list[Any], options: QueryOptions
    ) -> list[DockerNetworkEntry] | DockerNetworkEntry | int:
        if not await validate_state(self, False):
            networks_data: list[dict[str, Any]] = []
        else:
            networks_data = [
                {
                    k: network.get(k) for k in (
                        'ipam', 'labels', 'created', 'driver', 'id', 'name', 'scope', 'short_id',
                    )
                }
                for network in await self.to_thread(list_networks)
            ]

        result = filter_list(networks_data, filters, options.model_dump())
        if isinstance(result, int):
            return result
        if isinstance(result, dict):
            return self._to_entry(result)
        if isinstance(result, list):
            return [self._to_entry(row) for row in result]
        return result

    async def get_instance(self, id_: str, extra: dict[str, Any] | None = None) -> DockerNetworkEntry:
        results = await self.query([['id', '=', id_]], QueryOptions())
        if not isinstance(results, list) or not results:
            raise InstanceNotFound(f'DockerNetwork {id_} does not exist')
        return results[0]

    async def interfaces_mapping(self) -> list[str]:
        try:
            networks = await self.query([], QueryOptions())
            if isinstance(networks, list):
                return [f'br-{network.short_id}' for network in networks]
            return []
        except Exception as e:
            self.logger.error('Failed to get docker interfaces mapping: %s', e)
            return []
