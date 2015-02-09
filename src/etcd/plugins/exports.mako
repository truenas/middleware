<%
    import itertools

    def dataset_name(share):
        pool, dataset, path = dispatcher.call_sync("volumes.decode_path", share["target"])
        return dataset

    def grouped_shares():
        shares = dispatcher.call_sync("shares.query", [("type", "=", "nfs")])
        for key, items in itertools.groupby(shares, dataset_name):
            paths = ' '.join(map(lambda i: i["target"], items))
            opts = ""
            yield paths, opts

    def opts(share):
        if not 'properties' in share:
            return ''

        result = []
        properties = share['properties']

        if properties.get('alldirs'):
            result.append('-alldirs')

        if properties.get('maproot'):
            result.append('-maproot={0}'.format(properties['maproot']))

        for host in properties.get('hosts', []):
            result.append(host)
%>\
% for paths, opts in grouped_shares():
${paths} ${opts}
% endfor