import itertools


def grouper(iterable, n, *, incomplete='fill', fillvalue=None):
    "Collect data into non-overlapping fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, fillvalue='x') --> ABC DEF Gxx
    # grouper('ABCDEFG', 3, incomplete='strict') --> ABC DEF ValueError
    # grouper('ABCDEFG', 3, incomplete='ignore') --> ABC DEF
    args = [iter(iterable)] * n
    if incomplete == 'fill':
        return itertools.zip_longest(*args, fillvalue=fillvalue)
    if incomplete == 'strict':
        return zip(*args, strict=True)
    if incomplete == 'ignore':
        return zip(*args)
    else:
        raise ValueError('Expected fill, strict, or ignore')


def infinite_multiplier_generator(multiplier, max_value, initial_value):
    cur = initial_value
    while True:
        yield cur
        next_val = cur * multiplier
        if next_val <= max_value:
            cur = next_val


def batched(iterable, n):
    """
    Batch data from the `iterable` into tuples of length `n`. The
    last batch may be shorter than `n`.

    batched iter recipe from python 3.11 documentation. Python 3.12 adds a
    cpython variant of this to `itertools` and so this method should be
    replaced when TrueNAS python version upgrades to 3.12.
    """
    if n < 1:
        raise ValueError('n must be at least one')

    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch
