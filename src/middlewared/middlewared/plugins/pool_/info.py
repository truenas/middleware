from middlewared.service import private, Service


class PoolService(Service):

    @private
    def find_disk_from_topology(self, label, pool, options=None):
        options = options or {}
        include_top_level_vdev = options.get('include_top_level_vdev', False)
        include_siblings = options.get('include_siblings', False)

        check = []
        found = None
        for root, children in pool['topology'].items():
            check.append((root, children))

        while check and not found:
            root, children = check.pop()
            for c in children:
                if c['type'] == 'DISK':
                    if label in (c['path'].replace('/dev/', ''), c['guid']):
                        found = (root, c)
                        break
                elif include_top_level_vdev and c['guid'] == label:
                    found = (root, c)
                    break

                if c['children']:
                    check.append((root, c['children']))

            if found is not None and include_siblings:
                found = (found[0], found[1], children)

        return found
