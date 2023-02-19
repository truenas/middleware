from middlewared.schema import Dict
from middlewared.service import filterable, filterable_returns, Service
from middlewared.utils import filter_list


class AppService(Service):

    @filterable
    @filterable_returns(Dict(

    ))
    def available(self, filters, options):
        results = []

        return filter_list(results, filters, options)
