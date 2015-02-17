<%
    def opts(share):
        if not 'properties' in share:
            return ''

        result = []
        properties = share['properties']

        if properties.get('alldirs'):
            result.append('-alldirs')

        if properties.get('maproot-user'):
            result.append('-maproot={0}'.format(properties['maproot-user']))

        elif properties.get('mapall-user'):
            result.append('-mapall={0}'.format(properties['mapall-user']))

        for host in properties.get('hosts', []):
            result.append(host)

        return result
%>\
% for share in dispatcher.call_sync("shares.query", [("type", "=", "nfs")]):
${share["target"]} ${opts(share)}
% endfor