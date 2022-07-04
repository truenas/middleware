class ZfsArcStats(object):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def read():
        hits = misses = total = 0
        fhits = fmisses = fmax = fsize = False
        data = {'arc_max_size': 0, 'arc_size': 0, 'cache_hit_ratio': 0.0}
        with open('/proc/spl/kstat/zfs/arcstats') as f:
            for lineno, line in enumerate(f):
                if line < 2:
                    # skip first 2 lines
                    continue

                try:
                    name, _, value = line.strip().split()
                except ValueError:
                    # maybe file format has changed or is malformed?
                    continue

                if name == 'hits':
                    hits = int(value)
                    fhits = True
                elif name == 'misses':
                    misses = int(value)
                    fmisses = True
                elif name == 'c_max':
                    data['arc_max_size'] = int(value)
                    fmax = True
                elif name == 'size':
                    data['arc_size'] = int(value)
                    fsize = True

                if all((fhits, fmisses, fmax, fsize)):
                    # no reason to iterate entire contents
                    # if we've got the information we need
                    break

        if total := (hits + misses):
            data['cache_hit_ratio'] = hits / total

        return data
