import asyncio
from dns.asyncresolver import Resolver
from io import StringIO

from middlewared.service import private, Service, ValidationError
from middlewared.schema import accepts, returns, IPAddr, Dict, Int, List, Str, Ref, OROperator
from middlewared.utils import filter_list


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

    @accepts(Dict(
        'lookup_data',
        List('names', items=[Str('name')], required=True),
        List(
            'record_types',
            items=[Str('record_type', default='A', enum=['A', 'AAAA', 'SRV', 'CNAME'])],
            default=['A', 'AAAA']
        ),
        Dict(
            'dns_client_options',
            List('nameservers', items=[IPAddr("ip")], default=[]),
            Int('lifetime', default=12),
            Int('timeout', default=4),
            register=True
        ),
        Ref('query-filters'),
        Ref('query-options'),
        Str('throw_exception_on', default='host_failure', enum=['never', 'any_failure', 'host_failure', 'all_failure']),
    ))
    @returns(OROperator(
        List(
            'rdata_list_srv',
            items=[
                Dict(
                    Str('name'),
                    Int('priority'),
                    Int('weight'),
                    Int('port'),
                    Str('class'),
                    Str('type'),
                    Int('ttl'),
                    Str('target'),
                )
            ],
        ),
        List(
            'rdata_list_cname',
            items=[
                Dict(
                    Str('name'),
                    Str('class'),
                    Str('type'),
                    Int('ttl'),
                    Str('target'),
                )
            ],
        ),
        List(
            'rdata_list',
            items=[
                Dict(
                    Str('name'),
                    Str('class'),
                    Str('type'),
                    Int('ttl'),
                    IPAddr('address'),
                )
            ],
        ),
        name='record_list',
    ))
    async def forward_lookup(self, data):
        """
        Rules: We can combine 'A' and 'AAAA', but 'SRV' and 'CNAME' must be singular.
        NB1: By default raise_error=True and forward_lookup will return on the _first_ exception.
             If that is not desired then use raise_error=False
        NB2: With raise_error=False all results are returned and resolve attempts that
             generate an exception are returned as an empty list
        """
        single_rtypes = ['CNAME', 'SRV']
        output = []
        options = data['dns_client_options']

        if (len(data['record_types']) > 1) and (set(single_rtypes) & set(data['record_types'])):
            raise ValidationError(
                # 'dnclient.mcg_forward_lookup',
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

        # never - squash all failures
        # host  - raise if all tests for a name fail  (default case)
        # any   - raise on any failure
        # all   - raise if all tests for all 'names' fail
        if failures:
            if data['throw_exception_on'] == 'host_failure':
                for h in data['names']:
                    fph = len(failuresPerHost[h]) if failuresPerHost.get(h) is not None else 0
                    if fph == len(data['record_types']):
                        raise failuresPerHost[h][0]
            elif data['throw_exception_on'] == 'any_failure':
                raise failures[0]
            elif data['throw_exception_on'] == 'all_failure':
                if len(data['names']) * len(data['record_types']) == len(failures):
                    raise failures[0]

        return filter_list(output, data['query-filters'], data['query-options'])

    @accepts(Dict(
        'lookup_data',
        List("addresses", items=[IPAddr("address")], required=True),
        Ref('dns_client_options'),
        Ref('query-filters'),
        Ref('query-options'),
    ))
    @returns(List(
        'rdata_list',
        items=[
            Dict(
                Str('name'),
                Str('class'),
                Str('type'),
                Int('ttl'),
                Str('target'),
            )
        ]
    ))
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
