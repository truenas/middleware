from middlewared.service import private, Service


class PoolService(Service):

    @private
    def find_disk_from_topology(self, label, pool):
        check = []
        found = None
        for root, children in pool['topology'].items():
            check.append((root, children))

        while check:
            root, children = check.pop()
            for c in children:
                if c['type'] == 'DISK':
                    if label in (c['path'].replace('/dev/', ''), c['guid']):
                        found = (root, c)
                        break
                if c['children']:
                    check.append((root, c['children']))
        return found
