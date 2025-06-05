class NumericSet:
    def __call__(self, value):
        parse_numeric_set(value)


def parse_numeric_set(value):
    if value == '':
        return []

    cpus = {}
    parts = value.split(',')
    for part in parts:
        part = part.split('-')
        if len(part) == 1:
            cpu = int(part[0])
            cpus[cpu] = None
        elif len(part) == 2:
            start = int(part[0])
            end = int(part[1])
            if start >= end:
                raise ValueError(f'End of range has to greater that start: {start}-{end}')
            for cpu in range(start, end + 1):
                cpus[cpu] = None
        else:
            raise ValueError(f'Range has to be in format start-end: {part}')

    return list(cpus)
