import enum
from dns.asyncresolver import Resolver
from io import StringIO

from middlewared.service import private, Service
from middlewared.schema import accepts, returns, IPAddr, Dict, Int, List, Bool, Str, Ref, OROperator
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

        r.timeout=options['timeout']

        return r

    @accepts(Dict(
        'lookup_data',
        Str('name', required=True),
        Str('record_type', required=True, enum=['A', 'AAAA', 'SRV']),
        Dict(
            'dns_client_options',
            List('nameservers', items=[IPAddr("ip")], default=[]),
            Int('lifetime', default=12),
            Int('timeout', default=4),
            register=True
        ),
        Ref('query-filters'),
        Ref('query-options'),
    ))
    @returns(OROperator(
        List(
            'rdata_list_srv',
            items=[
                Dict(
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
        options = data['dns_client_options']

        r = await self.get_resolver(options)
        r.timeout=options['timeout']

        ans = await r.resolve(
            data['name'],
            rdtype=data['record_type'],
            lifetime=options['lifetime']
        )
        ttl = ans.response.answer[0].ttl

        if data['record_type'] == 'SRV':
            output = [{
                "priority": i.priority,
                "weight": i.weight,
                "port": i.port,
                "class": i.rdclass.name,
                "type": i.rdtype.name,
                "ttl": ttl,
                "target": i.target.to_text()
            } for i in ans.response.answer[0].items]
        else:
            name = ans.response.answer[0].name.to_text()
            output = [{
                "name": name,
                "class": i.rdclass.name,
                "type": i.rdtype.name,
                "ttl": ttl,
                "address": i.address,
            } for i in ans.response.answer[0].items]

        return filter_list(output, data['query-filters'], data['query-options'])

    @accepts(Dict(
        'lookup_data',
        IPAddr("address", required=True),
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
        options = data['dns_client_options']

        r = await self.get_resolver(options)
        r.timeout=options['timeout']

        ans = await r.resolve_address(
            data['address'],
            lifetime=options['lifetime']
        )
        ttl = ans.response.answer[0].ttl
        name = ans.response.answer[0].name.to_text()

        output = [{
            "name": name,
            "class": i.rdclass.name,
            "type": i.rdtype.name,
            "ttl": ttl,
            "target": i.target.to_text(),
        } for i in ans.response.answer[0].items]

        return filter_list(output, data['query-filters'], data['query-options'])
