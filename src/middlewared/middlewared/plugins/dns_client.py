import asyncio
from dns.asyncresolver import Resolver
from io import StringIO
from typing import Literal

from pydantic import Field

from middlewared.api import api_method
from middlewared.api.base import BaseModel, single_argument_args, IPvAnyAddress, Excluded, excluded_field
from middlewared.api.current import QueryFilters, QueryOptions
from middlewared.service import private, Service, ValidationError
from middlewared.utils.filter_list import filter_list


class DNSClientOptions(BaseModel):
    nameservers: list[IPvAnyAddress] = []
    lifetime: int = 12
    timeout: int = 4
    raise_error: Literal['NEVER', 'ANY_FAILURE', 'HOST_FAILURE', 'ALL_FAILURE'] = 'HOST_FAILURE'


class DNSClientCnameLookupItem(BaseModel):
    name: str
    class_: str = Field(alias='class')
    type: str
    ttl: int
    target: str


class DNSClientLookupItem(DNSClientCnameLookupItem):
    target: Excluded = excluded_field()
    address: IPvAnyAddress


class DNSClientSrvLookupItem(DNSClientCnameLookupItem):
    priority: int
    weight: int
    port: int


@single_argument_args('data')
class DNSClientForwardLookupArgs(BaseModel):
    names: list[str]
    record_types: list[Literal['A', 'AAAA', 'SRV', 'CNAME']] = ['A', 'AAAA']
    dns_client_options: DNSClientOptions = Field(default_factory=DNSClientOptions)
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default_factory=QueryOptions)


class DNSClientForwardLookupResult(BaseModel):
    result: list[DNSClientCnameLookupItem] | list[DNSClientLookupItem] | list[DNSClientSrvLookupItem]


@single_argument_args('data')
class DNSClientReverseLookupArgs(BaseModel):
    addresses: list[IPvAnyAddress]
    dns_client_options: DNSClientOptions = Field(default_factory=DNSClientOptions)
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default_factory=QueryOptions)


class DNSClientReverseLookupResult(BaseModel):
    result: list[DNSClientCnameLookupItem]


class DNSClient(Service):
    class Config:
        private = True

    @private
    async def get_resolver(self, options):
        if options['nameservers']:
            mem_resolvconf = StringIO()
            for n in options['nameservers']:
                mem_resolvconf.write(f"nameserver {n}\n")

            mem_resolvconf.seek(0)
            r = Resolver(mem_resolvconf)
        else:
            r = Resolver()

        r.timeout = options['timeout']

        return r

    @private
    async def resolve_name(self, name, rdtype, options):
        r = await self.get_resolver(options)

        if rdtype == 'PTR':
            ans = await r.resolve_address(
                name,
                lifetime=options['lifetime']
            )
        else:
            ans = await r.resolve(
                name, rdtype,
                lifetime=options['lifetime']
            )

        return ans

    @api_method(DNSClientForwardLookupArgs, DNSClientForwardLookupResult, private=True)
    async def forward_lookup(self, data):
        """
        Rules: We can combine 'A' and 'AAAA', but 'SRV' and 'CNAME' must be singular.
        NB1: By default record_types is ['A', 'AAAA'] and if selected will return both 'A' and 'AAAA' records
             for hosts that support both.
        NB2: By default raise_error is 'HOST_FAILURE', i.e. raise exception if all tests for a name fail
        NB3: With raise_error as 'NEVER' all results are returned and resolve attempts that
             generate an exception are returned as an empty list
        """
        single_rtypes = ['CNAME', 'SRV']
        output = []
        options = data['dns_client_options']

        if (len(data['record_types']) > 1) and (set(single_rtypes) & set(data['record_types'])):
            raise ValidationError(
                'dnclient.forward_lookup',
                f'{single_rtypes} cannot be combined with other rtypes in the same request'
            )

        results = await asyncio.gather(*[
            self.resolve_name(h, rtype, options) for h in data['names'] for rtype in data['record_types']
        ], return_exceptions=True)

        failures = []
        failuresPerHost = {}
        for (h, rtype), ans in zip([(h, rtype) for h in data['names'] for rtype in data['record_types']], results):
            if isinstance(ans, Exception):
                failures.append(ans)
                failuresPerHost[h] = failuresPerHost.setdefault(h, [])
                failuresPerHost[h].append(ans)
            else:
                ttl = ans.response.answer[0].ttl
                name = ans.response.answer[0].name.to_text()

                # 'SRV' and 'CNAME' are special
                if rtype == 'SRV':
                    entries = [{
                        "name": name,
                        "priority": i.priority,
                        "weight": i.weight,
                        "port": i.port,
                        "class": i.rdclass.name,
                        "type": i.rdtype.name,
                        "ttl": ttl,
                        "target": i.target.to_text()
                    } for i in ans.response.answer[0].items if i.rdtype.name == rtype]
                elif rtype == 'CNAME':
                    entries = [{
                        "name": name,
                        "class": i.rdclass.name,
                        "type": i.rdtype.name,
                        "ttl": ttl,
                        "target": i.target.to_text(),
                    } for i in ans.response.answer[0].items if i.rdtype.name == rtype]
                else:  # The remaining options are 'A' and/or 'AAAA'
                    entries = [{
                        "name": name,
                        "class": i.rdclass.name,
                        "type": i.rdtype.name,
                        "ttl": ttl,
                        "address": i.address,
                    } for i in ans.rrset.items if i.rdtype.name == rtype]

                output.extend(entries)

        # NEVER - squash all failures
        # HOST  - raise if all tests for a name fail  (default case)
        # ANY   - raise on any failure
        # ALL   - raise if all tests for all 'names' fail
        if failures:
            if options['raise_error'] == 'HOST_FAILURE':
                for h in data['names']:
                    fph = len(failuresPerHost[h]) if failuresPerHost.get(h) is not None else 0
                    if fph == len(data['record_types']):
                        raise failuresPerHost[h][0]
            elif options['raise_error'] == 'ANY_FAILURE':
                raise failures[0]
            elif options['raise_error'] == 'ALL_FAILURE':
                if len(data['names']) * len(data['record_types']) == len(failures):
                    raise failures[0]

        return filter_list(output, data['query-filters'], data['query-options'])

    @api_method(DNSClientReverseLookupArgs, DNSClientReverseLookupResult, private=True)
    async def reverse_lookup(self, data):
        output = []
        options = data['dns_client_options']

        results = await asyncio.gather(*[
            self.resolve_name(i, 'PTR', options) for i in data['addresses']
        ])

        for ans in results:
            ttl = ans.response.answer[0].ttl
            name = ans.response.answer[0].name.to_text()

            entries = [{
                "name": name,
                "class": i.rdclass.name,
                "type": i.rdtype.name,
                "ttl": ttl,
                "target": i.target.to_text(),
            } for i in ans.response.answer[0].items]

            output.extend(entries)

        return filter_list(output, data['query-filters'], data['query-options'])
